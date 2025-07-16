import React, { useState, useEffect } from 'react';
// Adjust the import path according to your project structure
import { queryRecordList } from '../page/api'; 
import { getAuthConfig } from '../utils';

// Import Chart.js components
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, // For x-axis (risk buckets are categories)
  LinearScale,   // For y-axis (count)
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

// Register Chart.js components
ChartJS.register(
    CategoryScale, 
    LinearScale, 
    BarElement, 
    Title, 
    Tooltip, 
    Legend
);

// Function to generate colors based on risk level
const getRiskColor = (riskBucket) => {
    // Parse the risk bucket to get the upper bound
    const match = riskBucket.match(/(\d+\.\d+)-(\d+\.\d+)/);
    if (!match) return 'rgba(200, 200, 200, 0.6)'; // Default gray for unknown format
    
    const upperBound = parseFloat(match[2]);
    
    // Color gradient from blue/green (low risk) to dark red (high risk)
    if (upperBound <= 0.2) {
        return 'rgba(52, 168, 83, 0.7)'; // Green - Very Low Risk
    } else if (upperBound <= 0.4) {
        return 'rgba(66, 133, 244, 0.7)'; // Blue - Low Risk
    } else if (upperBound <= 0.6) {
        return 'rgba(251, 188, 4, 0.7)'; // Yellow/Orange - Medium Risk
    } else if (upperBound <= 0.8) {
        return 'rgba(234, 67, 53, 0.7)'; // Red - High Risk
    } else {
        return 'rgba(154, 0, 0, 0.8)'; // Dark Red - Very High Risk
    }
};

/**
 * RiskGraph component to display risk score distribution.
 * Props:
 * - filters (object): An object containing filters, expected to have at least
 * startDate and endDate. e.g., { startDate: 'YYYY-MM-DD', endDate: 'YYYY-MM-DD' }
 * Other filters like addrState or riskLevel can be passed if the backend supports them
 * for the "RiskDistribution" type.
 */
function RiskGraph({ filters }) {
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
                console.warn("RiskGraph: startDate or endDate is missing in the filters prop.", filters);
                setError("Date range (startDate, endDate) is required to fetch graph data.");
                setIsLoading(false);
                return;
            }
            
            try {
                console.log("RiskGraph: Fetching data with type 'RiskDistribution' and input:", recordInput);
                queryRecordList("getRiskDistribution", recordInput, authConfig).then((response) => {
                    // Filter out any "other" bucket and only keep buckets with numeric ranges
                    const filteredData = response.filter(item => {
                        // Check if the bucket has the expected numeric format
                        const hasNumericFormat = /^\d+\.\d+-\d+\.\d+$/.test(item.riskBucket);
                        // Also exclude any bucket containing "other" (case-insensitive)
                        const containsOther = item.riskBucket.toLowerCase().includes('other');
                        return hasNumericFormat && !containsOther;
                    });
                    setChartData(filteredData);
                    setIsLoading(false);
                });
            
            } catch (err) {
                console.error("Error explicitly thrown/rejected by queryRecordList for RiskGraph:", err);
                setError(err.message || "Failed to load risk distribution data due to an API error.");
                setChartData([]);
                setIsLoading(false);
            }
        };

        loadGraphData();

    }, [filters]);

    if (isLoading) return <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>Loading risk distribution...</p>;
    if (error) return <p style={{ color: '#e53e3e', textAlign: 'center', padding: '20px' }}>Error loading risk graph: {error}</p>;
    
    if (!chartData || chartData.length === 0) {
        return <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>No risk distribution data available for the selected filters.</p>;
    }

    // Sort chartData by risk bucket to ensure proper order
    const sortedChartData = [...chartData].sort((a, b) => {
        const aMatch = a.riskBucket.match(/(\d+\.\d+)/);
        const bMatch = b.riskBucket.match(/(\d+\.\d+)/);
        if (aMatch && bMatch) {
            return parseFloat(aMatch[1]) - parseFloat(bMatch[1]);
        }
        return 0;
    });

    // Prepare data for Chart.js with dynamic colors
    const chartJsFormattedData = {
        labels: sortedChartData.map(item => item.riskBucket),
        datasets: [{
            label: "Applications by Risk Score",
            data: sortedChartData.map(item => item.count),
            backgroundColor: sortedChartData.map(item => getRiskColor(item.riskBucket)),
            borderWidth: 0, // No borders
            barPercentage: 0.8,
            categoryPercentage: 0.9
        }]
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'x',
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Risk Score Range',
                },
                grid: {
                    display: false
                },
                ticks: {
                    font: {
                        size: 12
                    },
                    color: '#495057'
                }
            },
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Number of Applications'
                },
                ticks: {
                    stepSize: Math.max(1, Math.ceil(Math.max(0, ...sortedChartData.map(item => item.count)) / 10)),
                    font: {
                        size: 12
                    },
                    color: '#495057'
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                }
            }
        },
        plugins: {
            legend: { 
                display: false // Hide legend since we're using color coding
            },
            title: { 
                display: true, 
                text: "Risk Score Distribution",
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
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleFont: {
                    size: 14
                },
                bodyFont: {
                    size: 13
                },
                padding: 10,
                cornerRadius: 4,
                callbacks: {
                    label: function(context) {
                        const value = context.parsed.y;
                        const bucket = context.label;
                        
                        // Determine risk level text based on bucket
                        let riskLevel = '';
                        const match = bucket.match(/(\d+\.\d+)-(\d+\.\d+)/);
                        if (match) {
                            const upperBound = parseFloat(match[2]);
                            if (upperBound <= 0.2) riskLevel = ' (Very Low Risk)';
                            else if (upperBound <= 0.4) riskLevel = ' (Low Risk)';
                            else if (upperBound <= 0.6) riskLevel = ' (Medium Risk)';
                            else if (upperBound <= 0.8) riskLevel = ' (High Risk)';
                            else riskLevel = ' (Very High Risk)';
                        }
                        
                        return `${value} applications${riskLevel}`;
                    }
                }
            }
        }
    };

    return (
        <div style={{ height: '350px', padding: '10px', border: '1px solid #eee', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <Bar options={chartOptions} data={chartJsFormattedData} />
        </div>
    );
}

export default RiskGraph;