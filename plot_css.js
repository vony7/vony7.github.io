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


    // range bar chart
    // prepare missions data for chart
    var count = 0;
    var utc8now = Date.now() + 8 * 60 * 60 * 1000;// UTC+8
    // convert utc8now to time string
    var utc8now = new Date(utc8now).toISOString().slice(0, 19).replace('T', ' ');
    // only include missions with start time later than 2020
    const missions_css = missions.filter((mission) => Date.parse(mission.start) > Date.parse("2020/01/01 00:00:00"));
    const missionDataPoints = missions_css.map((mission) => {
        if (mission.end === "0") {
            mission.end = utc8now;
        }
        //console.log(count, mission.start, mission.end, mission.name)
        // type crew, color red, type cargo, color orange, type core, color green
        var color = "red";
        if (mission.type === "cargo") {
            color = "orange";
        } else if (mission.type === "core") {
            color = "green";
        }
        return {
            x: ++count,
            y: [Date.parse(mission.start), Date.parse(mission.end)],
            label: mission.name,
            color: color
        };
    });

// Calculate duration for each mission in days
const missionDataPointsWithDuration = missionDataPoints.map(point => {
    const startTime = new Date(point.y[0]);
    const endTime = new Date(point.y[1]);
    const durationInMilliseconds = endTime - startTime;
    const durationInDays = durationInMilliseconds / (1000 * 60 * 60 * 24); // Convert milliseconds to days
    const formattedDuration = durationInDays.toFixed(2) + " days"; // Format duration as a string
    return {
        x: point.x,
        y: point.y,
        label: point.label,
        color: point.color,
        duration: formattedDuration
    };
});
console.log(missionDataPointsWithDuration);
var chart2 = new CanvasJS.Chart("chartContainer2", {
    animationEnabled: true,
    exportEnabled: true,
    title: {
        text: "Missions"
    },
    axisX: {
        interval: 1,
    },
    axisY: {
        labelFormatter: function (e) {
            // Format the date as desired
            return CanvasJS.formatDate(e.value, "DD MMM");
        }
    },
    data: [{
        type: "rangeBar",
        showInLegend: false,
        yValueFormatString: "MMM DD",
        toolTipContent: {
            content: "{label}<br>Start: {y[0]}<br>End: {y[1]}<br>Duration: {duration}"
        },
        dataPoints: missionDataPointsWithDuration
    }]
});

chart2.render();

}
