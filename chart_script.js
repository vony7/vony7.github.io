var browsers = ["Chrome", "Safari"];

// Filter missions starting after 2021
var missions = cms_missions.filter(function(mission) {
    return new Date(mission.start).getFullYear() > 2020;
});

// Set up dimensions and margins
var margin = { top: 50, right: 30, bottom: 80, left: 160 };
var width  = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
var height = Math.max(missions.length * 28, 400) - margin.top - margin.bottom;

function parseDate(dateStr) { return Date.parse(dateStr); }

// Process missions
missions.forEach(function(mission, index) {
    mission.start = parseDate(mission.start);
    if (mission.end === "now") {
        mission.end = Date.now() + 12 * 60 * 60 * 1000;
    } else if (!mission.end || isNaN(parseDate(mission.end))) {
        mission.end = mission.start + 7 * 24 * 60 * 60 * 1000;
    } else {
        mission.end = parseDate(mission.end);
    }
    mission.duration = (mission.end - mission.start) / (1000 * 60 * 60 * 24);
});

// Base scales (never mutated — rescaleX uses these for zoom)
var xBase = d3.scaleTime()
    .domain([d3.min(missions, d => d.start), Date.now() + 12 * 60 * 60 * 1000])
    .range([0, width]);

var y = d3.scaleBand()
    .domain(missions.map(d => d.name))
    .range([0, height])
    .padding(0.15);

var colorScale = d3.scaleOrdinal()
    .domain(["core", "cargo", "crew", "rescue"])
    .range(["#4CAF50", "#FF9800", "#F44336", "#9C27B0"]);

var tooltip   = document.getElementById("tooltip");
var formatDate = d3.timeFormat("%Y-%m-%d %H:%M");

// Root SVG
var svg = d3.select("#gantt-chart")
    .attr("width",  width  + margin.left + margin.right)
    .attr("height", height + margin.top  + margin.bottom)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

// Clip path — keeps bars inside the chart area during zoom/pan
svg.append("defs").append("clipPath")
    .attr("id", "chart-clip")
    .append("rect")
    .attr("width",  width)
    .attr("height", height);

// Groups
var barsGroup   = svg.append("g").attr("clip-path", "url(#chart-clip)");
var labelsGroup = svg.append("g").attr("clip-path", "url(#chart-clip)");

// Draw bars
barsGroup.selectAll("rect")
    .data(missions)
    .enter().append("rect")
    .attr("x",      d => xBase(d.start))
    .attr("y",      d => y(d.name))
    .attr("width",  d => Math.max(0, xBase(d.end) - xBase(d.start)))
    .attr("height", y.bandwidth())
    .style("fill",  d => colorScale(d.type))
    .on("mouseover", function(event, d) {
        tooltip.innerHTML =
            "<b>" + d.name + "</b><br>" +
            "开始: " + formatDate(d.start) + "<br>" +
            "结束: " + formatDate(d.end)   + "<br>" +
            "历时: " + (d.duration ? d.duration.toFixed(1) + " 天" : "N/A");
        tooltip.style.left    = Math.min(event.pageX + 10, window.innerWidth - 200) + "px";
        tooltip.style.top     = (event.pageY - 28) + "px";
        tooltip.style.opacity = 0.9;
    })
    .on("mouseout", () => tooltip.style.opacity = 0);

// Duration labels
labelsGroup.selectAll("text")
    .data(missions)
    .enter().append("text")
    .attr("x", d => xBase(d.end) - 4)
    .attr("y", d => y(d.name) + y.bandwidth() / 2 + 4)
    .text(d => d.duration != null ? d.duration.toFixed(1) + "天" : "")
    .style("fill", "white")
    .style("font-size", "11px")
    .style("text-anchor", "end");

// X-axis
function makeXAxis(xScale) {
    return d3.axisBottom(xScale).tickFormat(d3.timeFormat("%Y-%m-%d"));
}

var xAxisG = svg.append("g")
    .attr("class", "x-axis")
    .attr("transform", "translate(0," + height + ")")
    .call(makeXAxis(xBase));

xAxisG.selectAll("text")
    .attr("transform", "rotate(-40)")
    .style("text-anchor", "end")
    .style("fill", "white");
xAxisG.selectAll("path, line").style("stroke", "white");

// X-axis title
svg.append("text")
    .attr("class", "x-label")
    .attr("x", width / 2)
    .attr("y", height + margin.bottom - 10)
    .attr("text-anchor", "middle")
    .style("fill", "white")
    .style("font-size", "13px")
    .text("日期");

// Y-axis
var yAxisG = svg.append("g")
    .attr("class", "y-axis")
    .call(d3.axisLeft(y));

yAxisG.selectAll("text").style("fill", "white").style("font-size", "12px");
yAxisG.selectAll("path, line").style("stroke", "white");

// Y-axis title
svg.append("text")
    .attr("class", "y-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -height / 2)
    .attr("y", -margin.left + 20)
    .attr("text-anchor", "middle")
    .style("fill", "white")
    .style("font-size", "13px")
    .text("任务");

// Chart title
svg.append("text")
    .attr("class", "chart-title")
    .attr("x", width / 2)
    .attr("y", -20)
    .attr("text-anchor", "middle")
    .style("font-size", "20px")
    .style("fill", "white")
    .text("中国空间站任务");

// Zoom — x-axis only, scroll wheel + drag
var zoom = d3.zoom()
    .scaleExtent([1, 30])
    .translateExtent([[0, 0], [width, height]])
    .extent([[0, 0], [width, height]])
    .on("zoom", function(event) {
        var newX = event.transform.rescaleX(xBase);

        xAxisG.call(makeXAxis(newX))
            .selectAll("text")
            .attr("transform", "rotate(-40)")
            .style("text-anchor", "end")
            .style("fill", "white");
        xAxisG.selectAll("path, line").style("stroke", "white");

        barsGroup.selectAll("rect")
            .attr("x",     d => newX(d.start))
            .attr("width", d => Math.max(0, newX(d.end) - newX(d.start)));

        labelsGroup.selectAll("text")
            .attr("x", d => newX(d.end) - 4);
    });

// Transparent overlay captures mouse/touch events for zoom
svg.append("rect")
    .attr("class", "zoom-rect")
    .attr("width",  width)
    .attr("height", height)
    .style("fill", "none")
    .style("pointer-events", "all")
    .call(zoom);

// Resize handler
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function updateChart() {
    width  = document.getElementById('chart-container').offsetWidth - margin.left - margin.right;
    height = Math.max(missions.length * 28, 400) - margin.top - margin.bottom;

    d3.select("#gantt-chart")
        .attr("width",  width  + margin.left + margin.right)
        .attr("height", height + margin.top  + margin.bottom);

    xBase.range([0, width]);
    y.range([0, height]);

    svg.select("#chart-clip rect").attr("width", width).attr("height", height);

    barsGroup.selectAll("rect")
        .attr("x",      d => xBase(d.start))
        .attr("y",      d => y(d.name))
        .attr("width",  d => Math.max(0, xBase(d.end) - xBase(d.start)))
        .attr("height", y.bandwidth());

    labelsGroup.selectAll("text")
        .attr("x", d => xBase(d.end) - 4)
        .attr("y", d => y(d.name) + y.bandwidth() / 2 + 4);

    xAxisG.attr("transform", "translate(0," + height + ")").call(makeXAxis(xBase))
        .selectAll("text").attr("transform", "rotate(-40)").style("text-anchor", "end").style("fill", "white");
    xAxisG.selectAll("path, line").style("stroke", "white");

    yAxisG.call(d3.axisLeft(y))
        .selectAll("text").style("fill", "white").style("font-size", "12px");
    yAxisG.selectAll("path, line").style("stroke", "white");

    svg.select(".x-label").attr("x", width / 2).attr("y", height + margin.bottom - 10);
    svg.select(".y-label").attr("x", -height / 2);
    svg.select(".chart-title").attr("x", width / 2);

    svg.select(".zoom-rect")
        .attr("width",  width)
        .attr("height", height)
        .call(zoom.translateExtent([[0, 0], [width, height]]).extent([[0, 0], [width, height]]));
}

window.addEventListener('resize', debounce(updateChart, 100));