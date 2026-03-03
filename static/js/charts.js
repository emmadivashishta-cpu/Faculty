document.addEventListener('DOMContentLoaded', function() {
    
    // Global Chart Defaults
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = "#6b7280";
    
    // Fetch data from API
    fetch('/api/charts')
        .then(response => response.json())
        .then(data => {
            
            // --- Admin Charts ---
            
            if (data.dept_performance && document.getElementById('adminDeptBarChart')) {
                const ctxDept = document.getElementById('adminDeptBarChart').getContext('2d');
                new Chart(ctxDept, {
                    type: 'bar',
                    data: {
                        labels: data.dept_performance.labels,
                        datasets: [{
                            label: 'Average Composite Score',
                            data: data.dept_performance.scores,
                            backgroundColor: 'rgba(59, 130, 246, 0.8)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1,
                            borderRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }
            
            if (data.score_dist && document.getElementById('adminDistPieChart')) {
                const ctxDist = document.getElementById('adminDistPieChart').getContext('2d');
                new Chart(ctxDist, {
                    type: 'bar',
                    data: {
                        labels: data.score_dist.labels,
                        datasets: [
                            {
                                label: 'Quality Score',
                                data: data.score_dist.quality,
                                backgroundColor: 'rgba(16, 185, 129, 0.8)',
                                borderRadius: 4
                            },
                            {
                                label: 'Impact Score',
                                data: data.score_dist.impact,
                                backgroundColor: 'rgba(59, 130, 246, 0.8)',
                                borderRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        indexAxis: 'y', // Horizontal stacked bar to fit names better and act as a Pie/Distribution alternative
                        scales: {
                            x: { stacked: true },
                            y: { stacked: true }
                        },
                        plugins: {
                            tooltip: { mode: 'index', intersect: false }
                        }
                    }
                });
            }
            
            // --- Faculty Charts ---
            
            if (data.radar && document.getElementById('facultyRadarChart')) {
                const ctxRadar = document.getElementById('facultyRadarChart').getContext('2d');
                new Chart(ctxRadar, {
                    type: 'radar',
                    data: {
                        labels: data.radar.labels,
                        datasets: [{
                            label: 'Your Impact',
                            data: data.radar.values,
                            backgroundColor: 'rgba(59, 130, 246, 0.2)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                            pointBorderColor: '#fff',
                            pointHoverBackgroundColor: '#fff',
                            pointHoverBorderColor: 'rgba(59, 130, 246, 1)',
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            r: {
                                angleLines: { display: true },
                                suggestedMin: 0,
                                suggestedMax: 10
                            }
                        }
                    }
                });
            }
            
            if (data.pubs_vs_cites && document.getElementById('facultyBarChart')) {
                const ctxBar = document.getElementById('facultyBarChart').getContext('2d');
                new Chart(ctxBar, {
                    type: 'doughnut',
                    data: {
                        labels: data.pubs_vs_cites.labels,
                        datasets: [{
                            data: data.pubs_vs_cites.values,
                            backgroundColor: [
                                'rgba(16, 185, 129, 0.8)',
                                'rgba(245, 158, 11, 0.8)'
                            ],
                            borderWidth: 0,
                            hoverOffset: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '70%',
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }
            
            // Mock Line Chart for Year-wise growth
            if (document.getElementById('facultyLineChart')) {
                const ctxLine = document.getElementById('facultyLineChart').getContext('2d');
                
                // Get current score to mock a realistic upward trajectory
                let currentScore = 5.0; // Fallback
                const scoreElement = document.querySelector('.badge.bg-primary .fw-bold');
                if (scoreElement) {
                    currentScore = parseFloat(scoreElement.innerText);
                }
                
                const mockData = [
                    Math.max(0, currentScore - 6.5),
                    Math.max(0, currentScore - 4.2),
                    Math.max(0, currentScore - 2.8),
                    Math.max(0, currentScore - 0.5),
                    currentScore
                ];
                
                new Chart(ctxLine, {
                    type: 'line',
                    data: {
                        labels: ['2020', '2021', '2022', '2023', '2024'],
                        datasets: [{
                            label: 'Total Score Growth',
                            data: mockData,
                            borderColor: 'rgba(245, 158, 11, 1)',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 4,
                            pointBackgroundColor: 'rgba(245, 158, 11, 1)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }
            
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
        });
});
