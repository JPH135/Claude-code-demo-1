/* Fintech Scanner — Dashboard JavaScript */

function initDashboard() {
    const table = $('#companies-table').DataTable({
        processing: true,
        serverSide: true,
        ajax: {
            url: '/api/companies',
            data: function(d) {
                d.category = $('#filter-category').val();
                d.country = $('#filter-country').val();
                d.stage = $('#filter-stage').val();
                d.search = $('#filter-search').val();
                d.new_only = $('#filter-new-only').is(':checked') ? '1' : '';
            }
        },
        columns: [
            {
                data: 'name',
                render: function(data, type, row) {
                    let html = '<a href="/company/' + row.slug + '" class="company-name-link">' + escapeHtml(data) + '</a>';
                    if (row.is_new) {
                        html += ' <span class="badge badge-new">NEW</span>';
                    }
                    if (row.hq_city) {
                        html += '<br><small class="text-muted">' + escapeHtml(row.hq_city) + '</small>';
                    }
                    return html;
                }
            },
            {
                data: 'hq_country',
                render: function(data) {
                    const flags = {
                        'United Kingdom': '\uD83C\uDDEC\uD83C\uDDE7',
                        'Germany': '\uD83C\uDDE9\uD83C\uDDEA',
                        'France': '\uD83C\uDDEB\uD83C\uDDF7',
                        'Netherlands': '\uD83C\uDDF3\uD83C\uDDF1',
                        'Sweden': '\uD83C\uDDF8\uD83C\uDDEA',
                        'Ireland': '\uD83C\uDDEE\uD83C\uDDEA',
                        'Spain': '\uD83C\uDDEA\uD83C\uDDF8',
                        'Italy': '\uD83C\uDDEE\uD83C\uDDF9',
                        'Switzerland': '\uD83C\uDDE8\uD83C\uDDED',
                        'Denmark': '\uD83C\uDDE9\uD83C\uDDF0',
                        'Norway': '\uD83C\uDDF3\uD83C\uDDF4',
                        'Finland': '\uD83C\uDDEB\uD83C\uDDEE',
                        'Belgium': '\uD83C\uDDE7\uD83C\uDDEA',
                        'Austria': '\uD83C\uDDE6\uD83C\uDDF9',
                        'Portugal': '\uD83C\uDDF5\uD83C\uDDF9',
                        'Estonia': '\uD83C\uDDEA\uD83C\uDDEA',
                        'Lithuania': '\uD83C\uDDF1\uD83C\uDDF9',
                        'Poland': '\uD83C\uDDF5\uD83C\uDDF1',
                    };
                    return (flags[data] || '') + ' ' + (data || '');
                }
            },
            {
                data: 'category',
                render: function(data) {
                    return '<span class="badge bg-light text-dark">' + escapeHtml(data || '') + '</span>';
                }
            },
            {
                data: 'stage',
                render: function(data) {
                    if (!data) return '';
                    const cls = 'stage-badge-' + data.toLowerCase().replace(/\s+/g, '');
                    return '<span class="badge ' + cls + '">' + escapeHtml(data) + '</span>';
                }
            },
            {
                data: 'employee_count',
                render: function(data, type, row) {
                    if (!data) return '<span class="text-muted">-</span>';
                    let html = formatNumber(data);
                    if (row.employee_growth_6m) {
                        const cls = row.employee_growth_6m > 0 ? 'text-success' : 'text-danger';
                        const sign = row.employee_growth_6m > 0 ? '+' : '';
                        html += '<br><small class="' + cls + '">' + sign + row.employee_growth_6m + '%</small>';
                    }
                    return html;
                }
            },
            {
                data: 'total_raised_display',
                render: function(data, type, row) {
                    if (type === 'sort') return row.total_raised_usd || 0;
                    return '<strong>' + escapeHtml(data) + '</strong>';
                }
            },
            {
                data: 'last_round_display',
                render: function(data, type, row) {
                    return '<small>' + escapeHtml(data) + '</small>';
                }
            },
            {
                data: 'next_raise_estimate',
                render: function(data, type, row) {
                    if (!data) return '<span class="text-muted">-</span>';
                    let cls = '';
                    if (row.next_raise_confidence === 'High') cls = 'text-success fw-semibold';
                    else if (row.next_raise_confidence === 'Medium') cls = 'text-warning';
                    return '<small class="' + cls + '">' + escapeHtml(data) + '</small>';
                }
            },
            {
                data: 'quality_score',
                className: 'text-center',
                render: function(data) {
                    if (!data) return '-';
                    let cls = 'score-low';
                    if (data >= 60) cls = 'score-high';
                    else if (data >= 30) cls = 'score-medium';
                    return '<span class="score-cell ' + cls + '">' + Math.round(data) + '</span>';
                }
            },
            {
                data: 'growth_signal',
                className: 'text-center',
                render: function(data) {
                    if (!data) return '-';
                    let cls = 'score-low';
                    if (data >= 60) cls = 'score-high';
                    else if (data >= 30) cls = 'score-medium';
                    return '<span class="score-cell ' + cls + '">' + Math.round(data) + '</span>';
                }
            },
            {
                data: null,
                orderable: false,
                render: function(data, type, row) {
                    let html = '';
                    if (row.website) {
                        html += '<a href="' + escapeHtml(row.website) + '" target="_blank" class="link-icon" title="Website"><i class="bi bi-globe"></i></a>';
                    }
                    if (row.linkedin_url) {
                        html += '<a href="' + escapeHtml(row.linkedin_url) + '" target="_blank" class="link-icon" title="LinkedIn"><i class="bi bi-linkedin"></i></a>';
                    }
                    return html;
                }
            },
        ],
        order: [[8, 'desc']],  // Sort by quality score descending
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100],
        language: {
            info: 'Showing _START_ to _END_ of _TOTAL_ companies',
            lengthMenu: 'Show _MENU_ companies',
            processing: '<div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div> Loading...',
        },
        dom: '<"row"<"col-sm-6"l><"col-sm-6">>rtip',
    });

    // Filter handlers — reload table on filter change
    $('#filter-category, #filter-country, #filter-stage').on('change', function() {
        table.ajax.reload();
    });

    $('#filter-new-only').on('change', function() {
        table.ajax.reload();
    });

    let searchTimeout;
    $('#filter-search').on('keyup', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(function() {
            table.ajax.reload();
        }, 400);
    });

    // Clear filters
    $('#btn-clear-filters').on('click', function() {
        $('#filter-category').val('');
        $('#filter-country').val('');
        $('#filter-stage').val('');
        $('#filter-search').val('');
        $('#filter-new-only').prop('checked', false);
        table.ajax.reload();
    });
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    if (!num) return '-';
    return num.toLocaleString();
}
