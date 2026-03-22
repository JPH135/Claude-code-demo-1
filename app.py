"""Fintech Investment Opportunity Scanner — Flask Application."""

import io
import csv
import logging
from datetime import datetime, timedelta

import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for

from config import Config
from database.db import init_db, get_session
from database.models import Company, FundingRound, NewsArticle, EmployeeSnapshot, ScanLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize database
    with app.app_context():
        init_db()

    # Start scheduler if enabled
    if Config.SCHEDULER_ENABLED:
        try:
            from scheduler import init_scheduler
            init_scheduler(app)
        except Exception as e:
            logger.warning(f"Scheduler failed to start: {e}")

    # ── Dashboard ─────────────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        session = get_session()
        try:
            stats = {
                "total_companies": session.query(Company).count(),
                "total_countries": session.query(Company.hq_country).distinct().count(),
                "total_raised": session.query(Company).with_entities(
                    Company.total_raised_usd
                ).all(),
                "categories": sorted(set(
                    c[0] for c in session.query(Company.category).distinct().all() if c[0]
                )),
                "countries": sorted(set(
                    c[0] for c in session.query(Company.hq_country).distinct().all() if c[0]
                )),
                "stages": sorted(set(
                    c[0] for c in session.query(Company.stage).distinct().all() if c[0]
                )),
            }
            # Calculate total raised
            total = sum(c[0] for c in stats["total_raised"] if c[0])
            if total >= 1e9:
                stats["total_raised_display"] = f"${total / 1e9:.1f}B"
            else:
                stats["total_raised_display"] = f"${total / 1e6:.0f}M"

            # New this week
            week_ago = datetime.utcnow() - timedelta(days=7)
            stats["new_this_week"] = session.query(Company).filter(
                Company.created_at >= week_ago
            ).count()

            # Recent scan
            last_scan = session.query(ScanLog).order_by(ScanLog.started_at.desc()).first()
            stats["last_scan"] = last_scan.started_at.strftime("%Y-%m-%d %H:%M") if last_scan else "Never"

            return render_template("dashboard.html", stats=stats)
        finally:
            session.close()

    # ── Company Detail ────────────────────────────────────────────────────
    @app.route("/company/<slug>")
    def company_detail(slug):
        session = get_session()
        try:
            company = session.query(Company).filter_by(slug=slug).first()
            if not company:
                return render_template("404.html", message="Company not found"), 404

            # Get funding round chart data
            rounds = sorted(company.funding_rounds, key=lambda r: r.announced_date or datetime.min.date())
            chart_data = {
                "labels": [r.announced_date.strftime("%b %Y") if r.announced_date else "Unknown" for r in rounds],
                "amounts": [r.amount_usd / 1_000_000 if r.amount_usd else 0 for r in rounds],
                "types": [r.round_type for r in rounds],
            }

            # Employee trend data
            snapshots = sorted(company.employee_snapshots, key=lambda s: s.snapshot_date)
            emp_chart = {
                "labels": [s.snapshot_date.strftime("%b %Y") for s in snapshots],
                "counts": [s.employee_count for s in snapshots],
            }

            # All unique investors
            all_investors = set()
            lead_investors = set()
            for fr in company.funding_rounds:
                for inv in fr.lead_investors:
                    lead_investors.add(inv)
                    all_investors.add(inv)
                for inv in fr.all_investors:
                    all_investors.add(inv)

            # Raise prediction context
            from processors.raise_predictor import RaisePredictor
            raise_context = RaisePredictor.get_stage_context(company.stage)

            return render_template(
                "company_detail.html",
                company=company,
                chart_data=chart_data,
                emp_chart=emp_chart,
                all_investors=sorted(all_investors),
                lead_investors=sorted(lead_investors),
                raise_context=raise_context,
            )
        finally:
            session.close()

    # ── News Feed ─────────────────────────────────────────────────────────
    @app.route("/news")
    def news_feed():
        session = get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=Config.NEWS_MAX_AGE_DAYS)
            articles = (
                session.query(NewsArticle)
                .join(Company)
                .filter(NewsArticle.published_date >= cutoff.date())
                .order_by(NewsArticle.published_date.desc())
                .limit(100)
                .all()
            )
            # Attach company names
            for article in articles:
                article.company_name = article.company.name
                article.company_slug = article.company.slug

            return render_template("news_feed.html", articles=articles)
        finally:
            session.close()

    # ── API: Companies (DataTables server-side) ───────────────────────────
    @app.route("/api/companies")
    def api_companies():
        session = get_session()
        try:
            query = session.query(Company)

            # Filters
            category = request.args.get("category", "")
            country = request.args.get("country", "")
            stage = request.args.get("stage", "")
            search = request.args.get("search[value]", "") or request.args.get("search", "")
            new_only = request.args.get("new_only", "")
            min_employees = request.args.get("min_employees", type=int)
            max_employees = request.args.get("max_employees", type=int)

            if category:
                query = query.filter(Company.category == category)
            if country:
                query = query.filter(Company.hq_country == country)
            if stage:
                query = query.filter(Company.stage == stage)
            if search:
                query = query.filter(Company.name.ilike(f"%{search}%"))
            if new_only:
                week_ago = datetime.utcnow() - timedelta(days=7)
                query = query.filter(Company.created_at >= week_ago)
            if min_employees:
                query = query.filter(Company.employee_count >= min_employees)
            if max_employees:
                query = query.filter(Company.employee_count <= max_employees)

            # Total count (for DataTables)
            total = session.query(Company).count()
            filtered = query.count()

            # Sorting
            order_col = request.args.get("order[0][column]", "0")
            order_dir = request.args.get("order[0][dir]", "desc")

            sort_map = {
                "0": Company.name,
                "1": Company.hq_country,
                "2": Company.category,
                "3": Company.stage,
                "4": Company.employee_count,
                "5": Company.total_raised_usd,
                "6": Company.last_round_date,
                "7": Company.quality_score,
            }
            sort_col = sort_map.get(order_col, Company.quality_score)
            if order_dir == "asc":
                query = query.order_by(sort_col.asc().nullslast())
            else:
                query = query.order_by(sort_col.desc().nullslast())

            # Pagination
            start = request.args.get("start", 0, type=int)
            length = request.args.get("length", 50, type=int)
            companies = query.offset(start).limit(length).all()

            data = []
            for c in companies:
                data.append({
                    "name": c.name,
                    "slug": c.slug,
                    "hq_country": c.hq_country,
                    "hq_city": c.hq_city,
                    "category": c.category,
                    "stage": c.stage,
                    "employee_count": c.employee_count,
                    "employee_growth_6m": c.employee_growth_6m,
                    "total_raised_usd": c.total_raised_usd,
                    "total_raised_display": c.total_raised_display,
                    "last_round_display": c.last_round_display,
                    "last_round_date": c.last_round_date.isoformat() if c.last_round_date else None,
                    "next_raise_estimate": c.next_raise_estimate,
                    "next_raise_confidence": c.next_raise_confidence,
                    "quality_score": c.quality_score,
                    "growth_signal": c.growth_signal,
                    "website": c.website,
                    "linkedin_url": c.linkedin_url,
                    "is_new": c.created_at and c.created_at >= datetime.utcnow() - timedelta(days=7),
                })

            return jsonify({
                "draw": request.args.get("draw", 1, type=int),
                "recordsTotal": total,
                "recordsFiltered": filtered,
                "data": data,
            })
        finally:
            session.close()

    # ── API: Company Detail ───────────────────────────────────────────────
    @app.route("/api/company/<slug>")
    def api_company_detail(slug):
        session = get_session()
        try:
            company = session.query(Company).filter_by(slug=slug).first()
            if not company:
                return jsonify({"error": "Not found"}), 404
            result = company.to_dict()
            result["funding_rounds"] = [r.to_dict() for r in company.funding_rounds]
            result["news_articles"] = [a.to_dict() for a in company.news_articles[:20]]
            return jsonify(result)
        finally:
            session.close()

    # ── Export ─────────────────────────────────────────────────────────────
    @app.route("/export/csv")
    def export_csv():
        session = get_session()
        try:
            companies = session.query(Company).order_by(Company.quality_score.desc()).all()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Name", "Country", "City", "Category", "Stage", "Founded",
                "Employees", "Employee Growth 6m%", "Total Raised ($)",
                "Last Round", "Last Round Date", "Next Raise Est.",
                "Quality Score", "Growth Signal", "Website", "LinkedIn",
                "Crunchbase", "Description",
            ])
            for c in companies:
                writer.writerow([
                    c.name, c.hq_country, c.hq_city, c.category, c.stage,
                    c.founded_year, c.employee_count, c.employee_growth_6m,
                    c.total_raised_usd, c.last_round_display,
                    c.last_round_date, c.next_raise_estimate,
                    c.quality_score, c.growth_signal,
                    c.website, c.linkedin_url, c.crunchbase_url, c.description,
                ])
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode("utf-8")),
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"fintech_scanner_{datetime.utcnow().strftime('%Y%m%d')}.csv",
            )
        finally:
            session.close()

    @app.route("/export/excel")
    def export_excel():
        session = get_session()
        try:
            companies = session.query(Company).order_by(Company.quality_score.desc()).all()
            data = []
            for c in companies:
                data.append({
                    "Name": c.name, "Country": c.hq_country, "City": c.hq_city,
                    "Category": c.category, "Stage": c.stage, "Founded": c.founded_year,
                    "Employees": c.employee_count, "Growth 6m%": c.employee_growth_6m,
                    "Total Raised ($)": c.total_raised_usd, "Last Round": c.last_round_display,
                    "Last Round Date": c.last_round_date, "Next Raise Est.": c.next_raise_estimate,
                    "Quality Score": c.quality_score, "Growth Signal": c.growth_signal,
                    "Website": c.website, "LinkedIn": c.linkedin_url,
                    "Description": c.description,
                })
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Fintech Companies")
            output.seek(0)
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"fintech_scanner_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            )
        finally:
            session.close()

    # ── Admin ─────────────────────────────────────────────────────────────
    @app.route("/admin/refresh", methods=["POST"])
    def admin_refresh():
        """Trigger a manual data refresh."""
        from processors.enricher import DataEnricher
        from processors.scorer import CompanyScorer
        from processors.raise_predictor import RaisePredictor

        log = ScanLog(job_name="manual_refresh")
        session = get_session()
        session.add(log)
        session.commit()

        try:
            enricher = DataEnricher()
            enricher.refresh_news_all()

            scorer = CompanyScorer()
            scorer.score_all()

            predictor = RaisePredictor()
            predictor.predict_all()

            log.status = "completed"
            log.completed_at = datetime.utcnow()
            session.commit()
        except Exception as e:
            log.status = "failed"
            log.error_msg = str(e)
            session.commit()
        finally:
            session.close()

        return redirect(url_for("dashboard"))

    @app.route("/admin/logs")
    def admin_logs():
        session = get_session()
        try:
            logs = session.query(ScanLog).order_by(ScanLog.started_at.desc()).limit(50).all()
            return render_template("admin_logs.html", logs=logs)
        finally:
            session.close()

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html", message="Page not found"), 404

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
