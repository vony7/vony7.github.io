// Assuming you have missionDataPointsWithDuration as defined earlier
import { missions } from './css_missions.js';

// Your chart code goes here

const ctx = document.getElementById('missionsChart').getContext('2d');

const data = missions.map(point => ({
    x: point.label,
    y: point.y[0], // Use the start time as the starting point
    duration: point.duration // Use the duration in days as a custom property
}));

const missionsChart = new Chart(ctx, {
    type: 'horizontalBar', // Use a horizontal bar chart for range data
    data: {
        datasets: [{
            data: data,
            backgroundColor: data.map(() => 'rgba(75, 192, 192, 0.2)'), // Customize the bar color
            borderColor: data.map(() => 'rgba(75, 192, 192, 1)'),
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            x: {
                type: 'linear',
                position: 'bottom',
                title: {
                    display: true,
                    text: 'Duration (Days)'
                },
                beginAtZero: true
            }
        },
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return `Start: ${context.parsed.y.toDateString()}<br>End: ${new Date(context.parsed.y + context.parsed.duration * 24 * 60 * 60 * 1000).toDateString()}<br>Duration: ${context.dataset.data[context.dataIndex].duration}`;
                    }
                }
            }
        }
    }
});

  