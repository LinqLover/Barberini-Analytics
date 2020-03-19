// THIS WORKS!!!!!!!!!!!!


"use strict";

import "core-js/stable";
import "./../style/visual.less";
import powerbi from "powerbi-visuals-api";
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;
import IVisual = powerbi.extensibility.visual.IVisual;
import DataView = powerbi.DataView;
import DataViewTable = powerbi.DataViewTable;
import DataViewValueColumns = powerbi.DataViewValueColumns;
import DataViewValueColumn = powerbi.DataViewValueColumn;
import PrimitiveValue = powerbi.PrimitiveValue;

//import 'sigma/build/plugins/sigma.parsers.json.require.js'; // file does not exist
//import '../node_modules/sigma/build/plugins/sigma.parsers.json.min.js'; // Browser: sigma is not declared, even if added to pbiviz.json/externalJS
//import * as sigma from 'sigma'; // Does only import a function, but not a module
//import {sigma} from 'sigma';
//const sigmaatlas = import('sigma/build/plugins/sigma.layout.forceAtlas2.min'); // Browser: ChunkLoadError (promise rejeted), even if added to pbiviz.json/externalJS
//const sigmaatlas = require('sigma/build/plugins/sigma.layout.forceAtlas2.min'); // Browser: uncaught sigma is not declared, even if added to pbiviz.json/externalJS
// The stuff above documents all fruiteless approaches to import the whole sigma module.
// PROBLEM: I failed on several ways to import sigma.parsers.gexfparser here. sigma should be a module, but is a public function from the module.
// See also here: https://github.com/jacomyal/sigma.js/issues/871#issuecomment-600577941
// And see also here: https://github.com/DefinitelyTyped/DefinitelyTyped/issues/34776

require("./js/sigma.min");
require("./js/sigma.forceatlas2");
require("./js/sigma.parseGexf");

// IMPORT TODO: This looks better now. If we cannot use TypeScript, we should declare sigma here as any.


export class Visual implements IVisual {
    
    private target: HTMLElement;
    private outerContainer: HTMLDivElement;
    private container: HTMLDivElement;
    
    private sigInst: any;
    
    constructor(options: VisualConstructorOptions) {
        console.log("Visual constructor", options, new Date().toLocaleString());
        this.target = options.element;
        
        this.outerContainer = document.createElement('div');
        this.outerContainer.id = 'sigma-example-parent';
        this.outerContainer.style.width = '100%';
        this.outerContainer.style.height = '100%';
        options.element.appendChild(this.outerContainer);
        
        this.container = document.createElement('div');
        this.container.id = 'foo';
        this.container.className = 'sigma-expand';
        this.container.style.width = '100%';
        this.container.style.height = '100%';
        this.outerContainer.appendChild(this.container);
        
        
        this.sigInst = (sigma as any).init(document.getElementById("foo"));
        this.sigInst.drawingProperties = {
            defaultLabelColor: '#f00',
            defaultLabelSize: 20,
            defaultLabelBGColor: '#eee',
            defaultLabelHoverColor: '#f00',
            labelThreshold: 4,
            defaultEdgeType: 'curve',
            edgeWeightInfluence: 0,
            minNodeSize: 0.5,
            maxNodeSize: 15,
            minEdgeSize: 0.3,
            maxEdgeSize: 1
        }
        this.sigInst.mouseProperties = {
            maxRatio: 4 // max zoom factor
        };
        this.sigInst.startForceAtlas2();
        this.sigInst.stopForceAtlas2();
        
        
        // TODO: Apply rest of sigma stuff here.
        
        //sigma.parsers.gefx('foo.gefx', sigInst);
        /*var gexfString = '<?gefx template="true"?>';
        var gexf = ( new window.DOMParser() ).parseFromString(gexfString, "text/xml");
        sigma.parseGexf(sigInst, gexf);
        sigInst.startForceAtlas2();
        sigInst.stopForceAtlas2();
        sigInst.activateFishEye().draw();*/
        //this.root = $("<div>");//.appendTo(this.target);
            /*.attr("drag-resize-disabled", "true")
            .css({
                "background_color": "red",
                "position": "absolute"
            });*/
        /*this.container = $('<div class="sigma-expand"></div>').appendTo(this.outerContainer)
            .attr("id", "foo")
            .css({
                "width": "100%",
                "height": "100%"
            });*/
        
        console.log("constructor done");
    }

    public update(options: VisualUpdateOptions) {
        console.log('Visual update', options, new Date().toLocaleString());
        
        const dataView: DataView = options.dataViews[0];
        const tableDataView: DataViewTable = dataView.table;
        
        if (!tableDataView) {
            return;
        }
        
        console.log(tableDataView.rows);
        // LATEST TODO: Process table here and translate reviews_gexf.py
        
        const gexfString = '<?xml version="1.0" encoding="UTF-8"?> <gexf xmlns="http://www.gexf.net/1.3" version="1.3" xmlns:viz="http://www.gexf.net/1.3/viz" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.gexf.net/1.3 http://www.gexf.net/1.3/gexf.xsd"> <graph defaultedgetype="undirected" mode="static"> <attributes class="node" mode="static"> <attribute id="Gender" title="Gender" type="string"></attribute> </attributes> <nodes> <node id="0" label="Myriel"> <attvalues> <attvalue for="Gender" value="M"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="-95.274315" y="-46.711082" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> <node id="1" label="Napoleon"> <attvalues> <attvalue for="Gender" value="M"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="-48.155075" y="45.006344" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> <node id="2" label="MlleBaptistine"> <attvalues> <attvalue for="Gender" value="F"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="-25.879744" y="61.14878" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> <node id="3" label="MmeMagloire"> <attvalues> <attvalue for="Gender" value="F"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="8.465163" y="13.662047" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> <node id="4" label="CountessDeLo"> <attvalues> <attvalue for="Gender" value="F"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="72.727455" y="-87.02954" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> <node id="5" label="Geborand"> <attvalues> <attvalue for="Gender" value="F"></attvalue> </attvalues> <viz:size value="1.0"></viz:size> <viz:position x="-93.04595" y="5.3092685" z="0.0"></viz:position> <viz:color r="153" g="153" b="153"></viz:color> </node> </nodes> <edges> <edge source="1" target="0"> <attvalues></attvalues> </edge> <edge source="2" target="0" weight="8.0"> <attvalues></attvalues> </edge> <edge source="3" target="0" weight="10.0"> <attvalues></attvalues> </edge> <edge source="3" target="2" weight="6.0"> <attvalues></attvalues> </edge> <edge source="4" target="0"> <attvalues></attvalues> </edge> <edge source="5" target="0"> <attvalues></attvalues> </edge> </edges> </graph> </gexf>';
        var gexf = new window.DOMParser().parseFromString(gexfString, "text/xml");
        
        this.sigInst.parseGexf(this.sigInst,    gexf);
        this.sigInst.draw(2, 2, 2);
        
        
        console.log("Update done");
    }
}
