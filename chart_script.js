// Define variable browsers (unused in this script, can be removed if unnecessary)
var browsers = ["Chrome", "Safari"];

// Filter missions starting after 2021
var missions = cms_missions.filter(function(mission) {
    var missionStartDate = new Date(mission.start);
    return missionStartDate.getFullYear() > 2020;
});

// Set up dimensions and margin
var margin = { top: 50, right: 30, bottom: 30, left: 100 };
var width = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
var height = Math.max(missions.length * 25, 600) - margin.top - margin.bottom; // Dynamically set height

// Function to parse date
function parseDate(dateStr) {
    return Date.parse(dateStr);
}

// Process missions and handle 'now' end dates
missions.forEach(function(mission, index) {
    mission.start = parseDate(mission.start);
    
    if (mission.end === "now") {
        mission.end = Date.now()+12*60*60*1000;
    } else if (!mission.end || isNaN(parseDate(mission.end))) {
        // Log a warning for missing or invalid end dates
        console.warn(`Mission with missing or invalid end date at index ${index}:`, mission);
        mission.end = mission.start + (7 * 24 * 60 * 60 * 1000); // Default: 7 days after start
    } else {
        mission.end = parseDate(mission.end);
    }

    // Calculate mission duration in days
    if (!isNaN(mission.start) && !isNaN(mission.end)) {
        mission.duration = (mission.end - mission.start) / (1000 * 60 * 60 * 24); // in days
    } else {
        console.error(`Invalid date values for mission at index ${index}:`, mission);
        mission.duration = null;
    }
});

// Initialize SVG and scales
var svg = d3.select("#gantt-chart")
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

var x = d3.scaleTime()
    .domain([d3.min(missions, d => d.start), Date.now()])
    .range([0, width]);

var y = d3.scaleBand()
    .domain(missions.map(d => d.name))
    .range([0, height])
    .padding(0.1);

var colorScale = d3.scaleOrdinal()
    .domain(missions.map(d => d.type))
    .range(["#4CAF50", "#FF9800", "#F44336"]); // Accessible color palette

var tooltip = document.getElementById("tooltip");
var formatDate = d3.timeFormat("%Y-%m-%d %H:%M:%S");

// Function to draw Gantt bars
function drawGanttBars() {
    svg.selectAll("rect")
        .data(missions)
        .enter().append("rect")
        .attr("x", d => !isNaN(d.start) ? x(d.start) : 0)
        .attr("y", d => y(d.name))
        .attr("width", d => !isNaN(d.end) && !isNaN(d.start) ? x(d.end) - x(d.start) : 0)
        .attr("height", y.bandwidth())
        .style("fill", d => colorScale(d.type))
        .on("mouseover", function(event, d) {
            tooltip.innerHTML = `
                <b>${d.name}</b><br>
                开始: ${formatDate(d.start)}<br>
                结束: ${formatDate(d.end)}<br>
                历时: ${d.duration ? d.duration.toFixed(2) + " 天" : "N/A"}
            `;
            tooltip.style.left = Math.min(event.pageX, window.innerWidth - tooltip.clientWidth) + "px";
            tooltip.style.top = (event.pageY - 28) + "px";
            tooltip.style.opacity = 0.9;
        })
        .on("mouseout", () => tooltip.style.opacity = 0);
}

// Function to add labels
function addLabels() {
    svg.selectAll("text")
        .data(missions)
        .enter().append("text")
        .attr("x", d => d.end && !isNaN(d.end) ? x(d.end) - 5 : x(d.start) + 5)
        .attr("y", d => y(d.name) + y.bandwidth() / 2 + 5)
        .text(d => d.duration != null ? d.duration.toFixed(2) + "天" : "")
        .style("fill", "white")
        .style("text-anchor", "end");
}

// Function to add axes
function addAxes() {
    svg.append("g")
        .attr("class", "x-axis")
        .attr("transform", "translate(0," + height + ")")
        .call(d3.axisBottom(x).tickFormat(d3.timeFormat("%Y-%m-%d")))
        .selectAll(".x-axis text").style("fill", "white");

    svg.append("g")
        .attr("class", "y-axis")
        .call(d3.axisLeft(y))
        .selectAll(".x-axis text").style("fill", "white");
}

// Function to add chart title
function addChartTitle() {
    svg.append("text")
        .attr("class", "chart-title")
        .attr("x", width / 2)
        .attr("y", -20)
        .attr("text-anchor", "middle")
        .text("中国空间站任务")
        .style("font-size", "24px")
        .style("fill", "white");
}

// Initial draw
drawGanttBars();
addLabels();
addAxes();
addChartTitle();

// Resize handler with debouncing
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function updateChart() {
    // Debugging: Log the missions data
    console.log("Missions data:", missions);

    // Recalculate width and height
    width = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
    height = Math.max(missions.length * 25, 600) - margin.top - margin.bottom;

    // Update the SVG container
    d3.select("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom);

    // Update scales
    x.range([0, width]);
    y.range([0, height]);

    // Update Gantt bars
    var bars = svg.selectAll("rect")
        .data(missions);

    bars.enter()
        .append("rect")
        .merge(bars)
        .attr("x", d => {
            console.log("Bar start:", d.start); // Debugging
            return x(d.start);
        })
        .attr("y", d => y(d.name))
        .attr("width", d => x(d.end) - x(d.start))
        .attr("height", y.bandwidth())
        .style("fill", d => colorScale(d.type));

    bars.exit().remove();

    // Update labels
    var labels = svg.selectAll("text")
        .data(missions);

    labels.enter()
        .append("text")
        .merge(labels)
        .attr("x", d => {
            console.log("Label end:", d.end); // Debugging
            return x(d.end) - 5;
        })
        .attr("y", d => y(d.name) + y.bandwidth() / 2 + 5)
        .text(d => d.duration != null ? d.duration.toFixed(2) + "天" : "")
        .style("fill", "white")
        .style("text-anchor", "end");

    labels.exit().remove();

    // Update axes
    svg.select(".x-axis")
        .attr("transform", "translate(0," + height + ")")
        .call(d3.axisBottom(x).tickFormat(d3.timeFormat("%Y-%m-%d")));

    svg.select(".y-axis").call(d3.axisLeft(y));
    svg.select(".chart-title").style("fill", "white");
}

window.addEventListener('resize', debounce(updateChart, 100));