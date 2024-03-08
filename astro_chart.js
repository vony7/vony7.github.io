//console.log("missions: ", cms_missions);
//console.log("astronauts: ", astronauts);
// select crew missions from missions
let crew_missions = [];
for (let i = 0; i < cms_missions.length; i++) {
    if (cms_missions[i].type == "crew") {
        crew_missions.push(cms_missions[i]);
    }
}
//console.log("crew_missions: ", crew_missions);

class Astronaut {
    constructor(_name,_uid) {
        this.name = _name;
        this.uid =_uid;
        this.missions = [];
        this.time = 0;
    }
    describe() {
        console.log('Astronaut: ', this.name);
    }
    addMission(mission) {
        this.missions.push(mission);
        this.time += mission.duration;
    }
}

class Mission {
    constructor(_name, _start, _end, _crew) {
        this.name = _name;
        this.start = Date.parse(_start);
        if (_end === "now") {
            this.end = Date.parse(new Date().toLocaleString("en-US", { timeZone: "Asia/Shanghai" }));
        } else {
            this.end = Date.parse(_end);
        }
        this.duration = this.end - this.start;
        this.crews = _crew;
        ////console.log("this.crews: ", this.crews);
        for (let i = 0; i < _crew.length; i++) {
            //find the astronaut object from crews
            for (let j = 0; j < crews.length; j++) {
                if (crews[j].name == _crew[i]) {
                    ////console.log("found: ", crews[j].name);
                    crews[j].addMission(this);
                }
            }
        }
    }
    describe() {
        console.log("Mission Name: ", this.name);
        console.log("Launch: ", this.start);
        console.log("Land: ", this.end);
        console.log("Crews: ", this.crew);
    }
}

/*Astronaut*/
let crews = [];
for (let i = 0; i < astronauts.length; i++) {
    let astro = astronauts[i];
    let new_astro = new Astronaut(astro.name,astro.uid);
    crews.push(new_astro);
}

let missions = [];
for (let i = 0; i < crew_missions.length; i++) {
    szm = new Mission(crew_missions[i].name, crew_missions[i].start, crew_missions[i].end, crew_missions[i].crew);
    missions.push(szm);
}
//console.log("missions:", missions)
//console.log("crews:", crews)

let data = [];
function generateColorMap(numColors) {
    const colorMap = [];
    for (let i = 0; i < numColors; i++) {
        const hue = (i / numColors) * 360;
        const color = `hsl(${hue}, 50%, 40%)`; // You can adjust the saturation and lightness as needed
        colorMap.push(color);
    }
    return colorMap;
}

const nummissions = crew_missions.length;
const colors = generateColorMap(nummissions);

// data for stacked column chart
for (let i = 0; i < nummissions; i++) { //missions
    let mission = missions[i];
    let dataPonts = [];
    for (let j = 0; j < crews.length; j++) { // crews
        let new_data = {
            y: 0,
            label: crews[j].name,
            color: colors[i], // Assign a color from the colormap
        };
        dataPonts.push(new_data);
    }
    
    // for each crew in mission[i].crew, find the index in crews
    for (let k = 0; k < mission.crews.length; k++) {
        let crew = mission.crews[k];
        //let index = crews.indexOf(crew);
        let index2 = 0;
        for (let l = 0; l < crews.length; l++) {
            //console.log("crews[l].name:", crews[l].name);
            if (crew == crews[l].uid) {
                index2 = l;
                break;
            }
        }
        //console.log("datapoints:", dataPonts[index2]);
        ////console.log("index:", index2);
        val = (mission.duration / 24 / 3600 / 1000).toFixed(2);
        ////console.log("mission.duration:", mission);
        ////console.log("val:", val);
        ////console.log("dp",{y:val*1,label:crew.name})
        dataPonts[index2] = { y: val * 1, label: crew.name }; // *1 to convert string to number
    }
    
    // prepare dataseries for each mission
    dataSeries = {
        type: "stackedColumn",
        name: mission.name,
        showInLegend: "true",
        axisYType: "secondary",
        dataPoints: dataPonts,
        color: colors[i], // Assign a color from the colormap
    };
    // if last mission, add indexLabel: "#total", indexLabelPlacement: "outside",
    if (i == crew_missions.length - 1) {
        dataSeries.indexLabel = "#total";
        dataSeries.indexLabelPlacement = "outside";
        // indexlabel font color
        dataSeries.indexLabelFontColor = "#ffffff";
        // indexlabel font size
        dataSeries.indexLabelFontSize = 12;
    }
    data.push(dataSeries);
}
//console.log("data:", data);


var options = {
    animationEnabled: true,
    //theme: "light3",
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
        maximum: 240,
        labelFontSize: 12,
        labelFontColor: "#ffffff",
    },
    toolTip: {
        shared: true,
        reversed: true,
        cornerRadius: 5,
        fontSize: 12,
        contentFormatter: function (e) {
            ////console.log(e);
            var content = " ";
            var total = 0;
            // include the name of the crew
            content += e.entries[0].dataPoint.label + "<br>";
            for (var i = 0; i < e.entries.length; i++) {
                if (e.entries[i].dataPoint.y != 0) {
                    content += e.entries[i].dataSeries.name + ": " + e.entries[i].dataPoint.y + "天<br>";
                    total += e.entries[i].dataPoint.y;
                }
            }
            content += "总计: " + total + "天";
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
// total number of astronauts
tot_astro = astronauts.length;
// total number of crew missions
tot_crew_missions = crew_missions.length;
// total number of astroauts flown to space
tot_astro_flown = 0;
for (let i =0;i<crew_missions.length;i++){
    tot_astro_flown += crew_missions[i].crew.length;
}
console.log("tot_astro:", tot_astro);
console.log("tot_crew_missions:", tot_crew_missions);
console.log("tot_astro_flown:", tot_astro_flown);
document.write("<p> 入轨总人次数: " + tot_astro_flown + "</p>");
document.write("<p> 入轨航天员总数: " + tot_astro + "</p>");
document.write("<p> 载人飞行任务总数: " + tot_crew_missions + "</p>");
// currently in space
let in_space = [];
// crew missions, end is "now"
for (let i = 0; i < crew_missions.length; i++) {
    if (crew_missions[i].end == "now") {
        in_space.push(crew_missions[i]);
    }
}
console.log("in_space:", in_space);
// current status,
//go through each in_space mission, find the crew, find astronaut name
let in_space_astronauts = [];
for (let i = 0; i < in_space.length; i++) {
    document.write("<p> 当前在轨任务: " + in_space[i].name + "</p>");
    for (let j = 0; j < in_space[i].crew.length; j++) {
        for (let k = 0; k < astronauts.length; k++) {
            if (in_space[i].crew[j] == astronauts[k].uid) {
                in_space_astronauts.push(astronauts[k].name);
            }
        }
    }
}
console.log("in_space_astronauts:", in_space_astronauts);
document.write("<p> 当前在轨人员: " + in_space_astronauts + "</p>");