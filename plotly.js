import { launchEvents } from './launch2023.js';
import { missions } from './css_missions.js';

//console.log(launchEvents);
// plot launch events by country
const country = launchEvents.map((event) => event.Country);
const countryCount = country.reduce((acc, curr) => {
    if (typeof acc[curr] === 'undefined') {
        acc[curr] = 1;
    } else {
        acc[curr] += 1;
    }
    return acc;
}
    , {});
//console.log(countryCount);
// name of country in countryCount
const countryName = Object.keys(countryCount);
//console.log(countryName);
// number of launches in countryCount
const countryNumber = Object.values(countryCount);
//console.log(countryNumber);


var data = [
    {
        x: countryName,
        y: countryNumber,
        type: 'bar',
        text: countryNumber.map(String),
        textposition: 'auto',
        hoverinfo: 'none',
    }
];

Plotly.newPlot('myDiv', data);

// Step Line Chart
const countries = launchEvents.map((event) => event.Country);
// unique countries
const uniqueCountries = [...new Set(countries)];
//console.log(uniqueCountries);
// for each country, create data points
const countryDataPoints = uniqueCountries.map((country) => {
    var count = 0;
    const countryLaunches = launchEvents.filter((event) => event.Country === country);
    const countryDataPoints = countryLaunches.map((event) => {
        return { x: new Date(event.DateTime), y: ++count, label: country };
    });
    return {
        x: countryDataPoints.map((dataPoint) => dataPoint.x),
        y: countryDataPoints.map((dataPoint) => dataPoint.y),
        mode: 'lines+markers',
        marker: { size: 4 },
        name: country,
        line: { shape: 'hv' },
        type: 'scatter'
    };
});

var layout = {
    legend: {
        y: 0.5,
        traceorder: 'reversed',
        font: { size: 16 },
        yref: 'paper'
    }
};

Plotly.newPlot('myDiv2', countryDataPoints, layout);

