import React, { useState, useEffect } from 'react';
// Adjust the import path according to your project structure
import { queryRecordList } from '../page/api'; 
import { getAuthConfig } from '../utils';
// Import Chart.js components
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  TimeScale // For x-axis time scale
} from 'chart.js';
import 'chartjs-adapter-date-fns'; // Adapter for date/time functionality

// Register Chart.js components
ChartJS.register(
    CategoryScale, 
    LinearScale, 
    BarElement, 
    Title, 
    Tooltip, 
    Legend, 
    TimeScale
);

/**
 * CountGraph component to display applications over time.
 * Props:
 * - filters (object): An object containing filters, expected to have at least
 * startDate and endDate. e.g., { startDate: 'YYYY-MM-DD', endDate: 'YYYY-MM-DD' }
 */
function CountGraph({ filters }) {
    const [chartData, setChartData] = useState([]); 
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const loadGraphData = async () => {
            setIsLoading(true);
            setError(null);
            setChartData([]); 

            const authConfig = getAuthConfig();
            if (!authConfig || !authConfig.authToken || authConfig.authType === 'NONE' || authConfig.authType === 'API_KEY_ERROR') {
                setError("Authentication is not configured. Cannot fetch chart data.");
                setIsLoading(false);
                return;
            }

            const recordInput = { ...filters }; 

            if (!recordInput.startDate || !recordInput.endDate) {
                console.warn("CountGraph: startDate or endDate is missing in the filters prop.", filters);
                setError("Date range (startDate, endDate) is required to fetch graph data.");
                setIsLoading(false);
                return;
            }
            
            try {
                console.log("CountGraph: Fetching data with type 'ApplicationsOverTime' and input:", recordInput);
                 queryRecordList("getApplicationsOverTime", recordInput, authConfig).then((response) => {
                    setChartData(response || []); 
                  });
            } catch (err) {
                console.error("Error explicitly thrown/rejected by queryRecordList:", err);
                setError(err.message || "Failed to load chart data due to an API error.");
                setChartData([]);
            } finally {
                setIsLoading(false);
            }
        };

        loadGraphData();

    }, [filters]); 

    if (isLoading) return <p>Loading application counts for graph...</p>;
    if (error) return <p style={{ color: 'red' }}>Error loading graph: {error}</p>;
    
    // Prepare data for Chart.js
    // The `chartData` state will hold an array like:
    // [{ timeGroup: "YYYY-MM-DDTHH:mm:ssZ", count: 10 }, ...]
    if (!chartData || chartData.length === 0) {
        return <p>No application count data available for the selected filters.</p>;
    }

    const chartJsFormattedData = {
        labels: chartData.map(item => new Date(item.timeGroup)), // Use Date objects for time scale
        datasets: [{
            label: "Applications per Hour",
            data: chartData.map(item => item.count),
            backgroundColor: 'rgba(54, 162, 235, 0.6)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1,
            barPercentage: 0.7, // Adjust bar width
            categoryPercentage: 0.8 // Adjust spacing between bars
        }]
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false, // Important for controlling height via a wrapper div
        scales: {
            x: {
                type: 'time', // Use time scale
                time: {
                    unit: 'hour', // Display unit
                    tooltipFormat: 'MMM d, yyyy h:mm a', // Format for tooltips (e.g., Jun 2, 2025 3:00 PM)
                    displayFormats: {
                        hour: 'h a' // Format for x-axis labels (e.g., 3 PM)
                    }
                },
                title: {
                    display: true,
                    text: 'Time of Day'
                },
                grid: {
                    display: false // Hide x-axis grid lines for a cleaner look
                }
            },
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Number of Applications'
                },
                ticks: {
                    stepSize: Math.max(1, Math.ceil(Math.max(...chartData.map(item => item.count)) / 10)) // Ensure integer steps
                }
            }
        },
        plugins: {
            legend: { 
                display: false // Hide legend since we're using color coding
            },
            title: { 
                display: true, 
                text: "Applications Over Time",
                padding: {
                    top: 10,
                    bottom: 20
                },
                font: {
                    size: 16
                }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                    title: function(tooltipItems) {
                        // Format the tooltip title to be more readable
                        if (tooltipItems.length > 0) {
                            const date = new Date(tooltipItems[0].parsed.x);
                            return date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: 'numeric', hour12: true });
                        }
                        return '';
                    }
                }
            }
        }
    };

    return (
        <div style={{ height: '350px', padding: '10px', border: '1px solid #eee', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
             {/* Ensure the chart has a defined height via its parent or directly */}
            <Bar options={chartOptions} data={chartJsFormattedData} />
        </div>
    );
}

export default CountGraph;