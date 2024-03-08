// Define a variable
var browsers = ["Chrome", "Safari"];
// missions includes css_mission from cms_missions that start after 2021
var missions = cms_missions.filter(function(mission) {
    var missionStartDate = new Date(mission.start);
    var year = missionStartDate.getFullYear();
    return year > 2020;
});
//console.log(missions)
// Set up the dimensions and margin
var margin = { top: 50, right: 30, bottom: 30, left: 100 };
var width = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
var height = 600 - margin.top - margin.bottom;

// Define x as a global scale
var x = d3.scaleTime()
    .domain([d3.min(missions, function (mission) { return mission.start; }), d3.max(missions, function (mission) { return mission.end; })])
    .range([0, width]);
// Create a function to set up the chart
function setupChart() {
    // Calculate the updated dimensions based on the container size
    width = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
    var containerHeight = height + margin.top + margin.bottom;

    // Update the width of the SVG
    svg.attr("width", width + margin.left + margin.right);

    // Recalculate the X-axis scale
    x.range([0, width]);

    // Redraw the Gantt bars
    svg.selectAll("rect")
        .attr("x", function (mission) { return x(mission.start); })
        .attr("width", function (mission) { return x(mission.end) - x(mission.start); });

    // Redraw the X-axis
    svg.select(".x-axis")
        .call(d3.axisBottom(x).tickFormat(d3.timeFormat("%Y-%m-%d")));

    // Adjust the chart container's height if necessary
    var newHeight = Math.max(containerHeight, height);
    d3.select("#chart-container").style("height", newHeight + "px");
}

// Create the SVG element
var svg = d3.select("#gantt-chart")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");


// Initialize the chart
setupChart();

// Handle window resize event to update the chart
window.addEventListener('resize', setupChart);


// Append an SVG element to the "gantt-chart" div
var svg = d3.select("#gantt-chart")
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

// Function to parse date and time
function parseDate(dateStr) {
    // Parse the date string, including the time zone (e.g., "2023-10-25 15:30:00 CST")
    const date = Date.parse(dateStr + " CST");
    return date;
}

// Process missions to handle 'now' end dates, parse mission dates, and calculate duration
missions.forEach(function (mission) {
    if (mission.end === "now") {
        // Set the end date to the current date and time in UTC
        mission.end = Date.parse((new Date()).toISOString()) + 14 * 60 * 60 * 1000;
    } else {
        mission.end = parseDate(mission.end);
    }

    mission.start = parseDate(mission.start);
    ////console.log(mission.start);
    mission.duration = (mission.end - mission.start) / (1000 * 60 * 60 * 24); // Calculate duration in days
    // Debugging code

    //console.log("Mission:", mission.name);
    //console.log("Start Date:", mission.start);
    //console.log("End Date:", mission.end);
    //console.log("Duration:", mission.duration);

});

// Calculate the range for the X-axis
var x = d3.scaleTime()
    .domain([d3.min(missions, function (mission) { return mission.start; }), new Date()])
    .range([0, width]);

// Calculate the range for the Y-axis
var y = d3.scaleBand()
    .domain(missions.map(function (mission) { return mission.name; }))
    .range([0, height])
    .padding(0.1);
// Create a color scale based on mission types
var colorScale = d3.scaleOrdinal()
    .domain(missions.map(function (mission) { return mission.type; }))
    .range(["green", "orange", "red"]);
var tooltip = document.getElementById("tooltip");
var formatDate = d3.timeFormat("%Y-%m-%d %H:%M:%S CST");

// Create the Gantt bars with different fill colors based on mission types
svg.selectAll("rect")
    .data(missions)
    .enter().append("rect")
    .attr("x", function (mission) { return x(mission.start); })
    .attr("y", function (mission) { return y(mission.name); })
    .attr("width", function (mission) { return x(mission.end) - x(mission.start); })
    .attr("height", y.bandwidth())
    .style("fill", function (mission) { return colorScale(mission.type); })
    .on("mouseover", function (event) {
        const mission = d3.select(this).datum();
        tooltip.innerHTML =
            mission.name + "<br>" +
            "开始: " + formatDate(mission.start) + "<br>" +
            "结束: " + formatDate(mission.end) + "<br>" +
            "历时: " + (mission.duration ? mission.duration.toFixed(2) + " 天" : "N/A");
        tooltip.style.textAlign = "left";
        tooltip.style.left = (event.pageX - tooltip.clientWidth) + "px";
        tooltip.style.top = (event.pageY - 28) + "px";
        tooltip.style.opacity = 0.8;
    })
    .on("mouseout", function (mission) {
        tooltip.style.opacity = 0;
    });


// Add labels to the bars with duration rounded to two decimal places
svg.selectAll("text")
    .data(missions)
    .enter().append("text")
    .attr("x", function (mission) { return x(mission.end) - 5; }) // Adjust the positioning for right alignment
    .attr("y", function (mission) { return y(mission.name) + y.bandwidth() / 2 + 5; })
    .text(function (mission) {
        return mission.duration.toFixed(2) + "天";
    })
    .style("fill", "white")
    .style("text-anchor", "end"); // Align the text to the start (right)

// Add X and Y axis
svg.append("g")
    .attr("class", "x-axis")
    .attr("transform", "translate(0," + height + ")")
    .call(d3.axisBottom(x).tickFormat(d3.timeFormat("%Y-%m-%d")));

svg.append("g")
    .attr("class", "y-axis")
    .call(d3.axisLeft(y));

// Add chart title
svg.append("text")
    .attr("x", width / 2)
    .attr("y", -5) // Adjust the y value as needed
    .attr("text-anchor", "middle")
    .text("中国空间站任务")
    .attr("class", "chart-title") // Add the class
    .style("font-size", "36px")// Set the font size
    .style("fill", "white"); // Set the text color to red

// Initialize the chart
setupChart();

// Handle window resize event to update the chart
window.addEventListener('resize', setupChart);
