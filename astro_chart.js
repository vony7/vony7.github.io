// select crew missions
let crew_missions = [];
for (let i = 0; i < cms_missions.length; i++) {
    if (cms_missions[i].type == "crew") {
        crew_missions.push(cms_missions[i]);
    }
}

class Astronaut {
    constructor(_name, _uid) {
        this.name = _name;
        this.uid = _uid;
        this.missions = [];
        this.time = 0;
    }
    describe() {
        console.log('Astronaut: ', this.name);
    }
    addMission(mission, durationOverride) {
        this.missions.push(mission);
        this.time += (durationOverride !== undefined) ? durationOverride : mission.duration;
    }
}

class Mission {
    constructor(_name, _mid, _start, _end, _crew) {
        this.name = _name;
        this.mid = _mid;
        this.start = Date.parse(_start);
        if (_end === "now") {
            this.end = Date.parse(new Date().toLocaleString("en-US", { timeZone: "Asia/Shanghai" }));
        } else {
            this.end = Date.parse(_end);
        }
        this.duration = this.end - this.start;
        this.crews = _crew;
        this.crewDurations = {};
        let overrides = returnOverrides[_mid] || {};
        for (let i = 0; i < _crew.length; i++) {
            let uid = _crew[i];
            let actualEnd = (overrides[uid] !== undefined) ? overrides[uid] : this.end;
            let actualDuration = actualEnd - this.start;
            this.crewDurations[uid] = actualDuration;
            for (let j = 0; j < crews.length; j++) {
                if (crews[j].uid == uid) {
                    crews[j].addMission(this, actualDuration);
                }
            }
        }
    }
    describe() {
        console.log("Mission Name: ", this.name);
        console.log("Launch: ", this.start);
        console.log("Land: ", this.end);
        console.log("Crews: ", this.crews);
    }
}

/*Astronaut*/
let crews = [];
for (let i = 0; i < astronauts.length; i++) {
    let astro = astronauts[i];
    let new_astro = new Astronaut(astro.name, astro.uid);
    crews.push(new_astro);
}

// Build returnOverrides: { launchMissionMid: { uid: returnTimestamp } }
// For each mission with return_crew, find the most recent launch mission for each uid
let returnOverrides = {};
for (let i = 0; i < crew_missions.length; i++) {
    let rm = crew_missions[i];
    if (!rm.return_crew || rm.return_crew.length === 0) continue;
    let returnEndTime = rm.end === "now"
        ? Date.parse(new Date().toLocaleString("en-US", { timeZone: "Asia/Shanghai" }))
        : Date.parse(rm.end);
    let returnStartTime = Date.parse(rm.start);
    for (let k = 0; k < rm.return_crew.length; k++) {
        let uid = rm.return_crew[k];
        // find the most recent launch mission for this uid before this return mission
        let bestLaunch = null;
        let bestLaunchTime = -Infinity;
        for (let j = 0; j < crew_missions.length; j++) {
            let lm = crew_missions[j];
            let lmStart = Date.parse(lm.start);
            if (lm.crew && lm.crew.includes(uid) && lmStart < returnStartTime && lmStart > bestLaunchTime) {
                bestLaunch = lm;
                bestLaunchTime = lmStart;
            }
        }
        if (bestLaunch) {
            if (!returnOverrides[bestLaunch.mid]) returnOverrides[bestLaunch.mid] = {};
            returnOverrides[bestLaunch.mid][uid] = returnEndTime;
        }
    }
}
console.log("returnOverrides:", returnOverrides);

let missions = [];
for (let i = 0; i < crew_missions.length; i++) {
    let m = crew_missions[i];
    if (m.crew.length > 0) {
        szm = new Mission(m.name, m.mid, m.start, m.end, m.crew);
        missions.push(szm);
    }
}

console.log("missions: ", missions);
console.log("crews: ", crews);
let data = [];
function generateColorMap(numColors) {
    const colorMap = [];
    for (let i = 0; i < numColors; i++) {
        const hue = (i / numColors) * 360;
        const color = `hsl(${hue}, 50%, 40%)`;
        colorMap.push(color);
    }
    return colorMap;
}

const nummissions = missions.length;
const colors = generateColorMap(nummissions);

// data for stacked column chart
for (let i = 0; i < nummissions; i++) {
    let mission = missions[i];
    let dataPonts = [];
    for (let j = 0; j < crews.length; j++) {
        let new_data = {
            y: 0,
            label: crews[j].name,
            color: colors[i],
        };
        dataPonts.push(new_data);
    }

    for (let k = 0; k < mission.crews.length; k++) {
        let crewUid = mission.crews[k];
        let index2 = 0;
        for (let l = 0; l < crews.length; l++) {
            if (crewUid == crews[l].uid) {
                index2 = l;
                break;
            }
        }
        let crewDuration = mission.crewDurations[crewUid] || mission.duration;
        val = (crewDuration / 24 / 3600 / 1000).toFixed(2);
        dataPonts[index2] = { y: val * 1, label: crews[index2].name };
    }

    dataSeries = {
        type: "stackedColumn",
        name: mission.name,
        showInLegend: "true",
        axisYType: "secondary",
        dataPoints: dataPonts,
        color: colors[i],
    };
    if (i == nummissions - 1) {
        dataSeries.indexLabel = "#total";
        dataSeries.indexLabelPlacement = "outside";
        dataSeries.indexLabelFontColor = "#ffffff";
        dataSeries.indexLabelFontSize = 12;
    }
    data.push(dataSeries);
}

let maxDuration = 0;
for (let i = 0; i < crews.length; i++) {
    if (crews[i].time > maxDuration) {
        maxDuration = crews[i].time;
    }
}
maxDuration = maxDuration / 24 / 3600 / 1000 + 10;
console.log("maxDuration:", maxDuration);

var options = {
    animationEnabled: true,
    backgroundColor: "#101312",
    title: {
        text: "中国航天员任务时间",
        fontsize: 12,
        fontColor: "#ffffff",
    },
    axisX: {
        title: "",
        interval: 1,
        labelFontSize: 12,
        labelFontColor: "#ffffff",
    },
    axisY2: {
        prefix: "",
        lineThickness: .5,
        maximum: maxDuration,
        labelFontSize: 12,
        labelFontColor: "#ffffff",
    },
    toolTip: {
        shared: true,
        reversed: true,
        cornerRadius: 5,
        fontSize: 12,
        contentFormatter: function (e) {
            var content = " ";
            var total = 0;
            content += e.entries[0].dataPoint.label + "<br>";
            for (var i = 0; i < e.entries.length; i++) {
                if (e.entries[i].dataPoint.y != 0) {
                    content += e.entries[i].dataSeries.name + ": " + e.entries[i].dataPoint.y + "天<br>";
                    total += e.entries[i].dataPoint.y;
                }
            }
            content += "总计: " + total.toFixed(2) + "天";
            return content;
        }
    },
    legend: {
        verticalAlign: "bottom",
        horizontalAlign: "center",
        fontSize: 12,
        fontColor: "#ffffff",
    },
    data: data
};
$("#chartContainer").CanvasJSChart(options);

// stats
tot_astro = astronauts.length;
tot_crew_missions = cms_missions.filter(m => m.type == "crew").length;
tot_astro_flown = 0;
for (let i = 0; i < crew_missions.length; i++) {
    if (crew_missions[i].type == "crew") {
        tot_astro_flown += crew_missions[i].crew.length;
    }
}
console.log("tot_astro:", tot_astro);
console.log("tot_crew_missions:", tot_crew_missions);
console.log("tot_astro_flown:", tot_astro_flown);
document.write("<p> 入轨总人次数: " + tot_astro_flown + "</p>");
document.write("<p> 入轨航天员总数: " + tot_astro + "</p>");
document.write("<p> 载人飞行任务总数: " + tot_crew_missions + "</p>");

// currently in space
let in_space = [];
for (let i = 0; i < crew_missions.length; i++) {
    if (crew_missions[i].end == "now") {
        in_space.push(crew_missions[i]);
    }
}
console.log("in_space:", in_space);
let in_space_astronauts = [];
for (let i = 0; i < in_space.length; i++) {
    document.write("<p> 当前在轨任务: " + in_space[i].name + "</p>");
    let allCrew = [...(in_space[i].crew || []), ...(in_space[i].return_crew || [])];
    allCrew = [...new Set(allCrew)];
    for (let j = 0; j < allCrew.length; j++) {
        for (let k = 0; k < astronauts.length; k++) {
            if (allCrew[j] == astronauts[k].uid) {
                in_space_astronauts.push(astronauts[k].name);
            }
        }
    }
}
console.log("in_space_astronauts:", in_space_astronauts);
document.write("<p> 当前在轨人员: " + in_space_astronauts + "</p>");