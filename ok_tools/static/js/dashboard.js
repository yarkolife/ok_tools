// Dashboard JavaScript functionality
// Note: Mobile sidebar functionality is now handled in base.html
// This file focuses on dashboard-specific features like charts, tooltips, and animations

window.dashboardGettext = window.dashboardGettext || window.gettext || function (str) { return str; };

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar functionality is now handled in base.html
    // This file focuses on dashboard-specific functionality
    // Set active sidebar link based on current page
    setActiveSidebarLink();

    // Initialize tooltips
    initializeTooltips();

    // Initialize charts if Chart.js is available and data is present
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }

    // Add fade-in animation to dashboard cards
    addFadeInAnimation();

    // Cleanup charts when page is unloaded
    window.addEventListener('beforeunload', cleanupCharts);
});

// Set active sidebar link based on current URL
function setActiveSidebarLink() {
    const currentPath = window.location.pathname;
    const sidebarLinks = document.querySelectorAll('.sidebar-link');

    sidebarLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (!href || href === '#') {
            return;
        }

        if (currentPath === href || currentPath.startsWith(`${href}/`)) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// Initialize Bootstrap tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize dashboard charts
function initializeCharts() {
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js is not loaded');
        return;
    }

    // Check if monthly stats data is available
    if (!window.monthlyStats || !window.monthlyStats.labels || !Array.isArray(window.monthlyStats.labels) || window.monthlyStats.labels.length === 0) {
        console.warn('Monthly stats data not available or empty, showing placeholder');
        console.log('Available monthly stats:', window.monthlyStats);
        showChartPlaceholder();
        return;
    }

    const ctx = document.getElementById('dashboardChart');
    if (ctx) {
        // Destroy existing chart if it exists and is a valid Chart.js instance
        if (window.dashboardChart && typeof window.dashboardChart.destroy === 'function') {
            try {
                window.dashboardChart.destroy();
            } catch (e) {
                console.warn('Error destroying existing chart:', e);
            }
        }

        // Check if dark theme is active
        const isDarkTheme = document.body.classList.contains('theme-dark') || 
                           document.documentElement.classList.contains('theme-dark') ||
                           window.getComputedStyle(document.body).backgroundColor === 'rgb(26, 26, 26)';

        // Create new chart with real data
        try {
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            color: isDarkTheme ? '#cccccc' : undefined
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: isDarkTheme ? '#cccccc' : undefined
                        },
                        grid: {
                            color: isDarkTheme ? 'rgba(255, 255, 255, 0.1)' : undefined
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            maxTicksLimit: 5,
                            color: isDarkTheme ? '#cccccc' : undefined
                        },
                        grid: {
                            color: isDarkTheme ? 'rgba(255, 255, 255, 0.1)' : undefined
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            };

            // Add background color for dark theme
            if (isDarkTheme) {
                chartOptions.plugins.legend.labels.color = '#cccccc';
            }

            window.dashboardChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: window.monthlyStats.labels || [],
                    datasets: [{
                        label: window.dashboardGettext('Licenses'),
                        data: window.monthlyStats.licenses || [],
                        borderColor: '#5e72e4',
                        backgroundColor: isDarkTheme ? 'rgba(94, 114, 228, 0.2)' : 'rgba(94, 114, 228, 0.1)',
                        tension: 0.4
                    }, {
                        label: window.dashboardGettext('Rentals'),
                        data: window.monthlyStats.rentals || [],
                        borderColor: '#2dce89',
                        backgroundColor: isDarkTheme ? 'rgba(45, 206, 137, 0.2)' : 'rgba(45, 206, 137, 0.1)',
                        tension: 0.4
                    }, {
                        label: window.dashboardGettext('Contributions'),
                        data: window.monthlyStats.contributions || [],
                        borderColor: '#f5365c',
                        backgroundColor: isDarkTheme ? 'rgba(245, 54, 92, 0.2)' : 'rgba(245, 54, 92, 0.1)',
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        } catch (e) {
            console.error('Error creating chart:', e);
            window.dashboardChart = null;
        }
    }
}

// Cleanup charts to prevent memory leaks
function cleanupCharts() {
    if (window.dashboardChart && typeof window.dashboardChart.destroy === 'function') {
        try {
            window.dashboardChart.destroy();
        } catch (e) {
            console.warn('Error destroying chart during cleanup:', e);
        }
        window.dashboardChart = null;
    }
}

// Show placeholder when chart data is not available
function showChartPlaceholder() {
    const chartContainer = document.querySelector('.chart-container');
    if (chartContainer) {
        chartContainer.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-bar-chart text-muted" style="font-size: 3rem;"></i>
                <p class="mt-3 text-muted">${window.dashboardGettext('No chart data available')}</p>
                <small class="text-muted">${window.dashboardGettext('Monthly statistics will appear here when data is available')}</small>
            </div>
        `;
    }
}

// Add fade-in animation to dashboard cards
function addFadeInAnimation() {
    const cards = document.querySelectorAll('.dashboard-card');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
            }
        });
    });

    cards.forEach(card => {
        observer.observe(card);
    });
}

// Utility function to show loading state
function showLoading(element) {
    if (element) {
        element.classList.add('loading');
        element.innerHTML += '<span class="spinner ms-2"></span>';
    }
}

// Utility function to hide loading state
function hideLoading(element) {
    if (element) {
        element.classList.remove('loading');
        const spinner = element.querySelector('.spinner');
        if (spinner) {
            spinner.remove();
        }
    }
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Utility function to format numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + window.dashboardGettext('M');
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + window.dashboardGettext('K');
    }
    return num.toString();
}

// Utility function to format currency
function formatCurrency(amount, currency = '€') {
    return currency + ' ' + amount.toLocaleString('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Export functions to global scope for use in other scripts
window.DashboardUtils = {
    showLoading,
    hideLoading,
    showNotification,
    formatNumber,
    formatCurrency
};
