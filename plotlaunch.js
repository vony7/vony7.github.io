import { launchEvents } from './launch2023.js';
import { missions } from './css_missions.js';
if (typeof browser === "undefined") {
    var browser = chrome;
}
//console.log(launchEvents);
//
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
//console.log(country,countryCount);
// create data points for chart
const dataPoints = Object.keys(countryCount).map((key) => {
    return { y: countryCount[key], label: key };
});
//console.log(dataPoints);

window.onload = function () {
    var chart1 = new CanvasJS.Chart("chartContainer1", {
        animationEnabled: true,
        title: {
            text: "Launch Record 2023"
        },
        axisX: {
            interval: 1
        },
        axisY2: {
            interlacedColor: "rgba(1,77,101,.2)",
            gridColor: "rgba(1,77,101,.1)",
            title: "Number of Launches"
        },
        data: [{
            type: "bar",
            name: "companies",
            axisYType: "secondary",
            color: "#014D65",
            dataPoints: dataPoints
        }]
    }
    );
    chart1.render();


    // Step Line Chart
    // countries in the launch events
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
            type: "stepLine",
            name: country,
            showInLegend: true,
            lineDashType: "solid",
            axisYType: "secondary",
            connectNullData: true,
            xValueFormatString: "MMM DD",
            dataPoints: countryDataPoints
        };
    });
}
