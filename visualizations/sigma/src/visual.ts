'use strict';

import './../style/visual.less';
import powerbi from 'powerbi-visuals-api';
import DataView = powerbi.DataView;
import DataViewTable = powerbi.DataViewTable;
import DataViewTableRow = powerbi.DataViewTableRow;
import IViewPort = powerbi.IViewport;
import IVisual = powerbi.extensibility.visual.IVisual;
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions = powerbi.extensibility.visual.VisualUpdateOptions;

import 'core-js/stable';
import * as math from 'mathjs';
import * as d3 from 'd3';

import './utils/arrayUtils';
import {histogram} from './histogram';
import {logExceptions} from './utils/logExceptions';
import * as mathUtils from './utils/mathUtils';
import './utils/mapUtils';
import * as sigmaUtils from './utils/sigmaUtils';
import './utils/stringUtils';

// WHY WE CANNOT IMPORT SIGMA.JS AS DEFINED IN NPM
// The problem is that sigma is always imported as a function rather than as a module.
// This makes it impossible to access sigma.parsers.gexf reliably, for example.
// Maybe this is related to Power BI's hacks to alias this, self and window?
// See also here: https://github.com/jacomyal/sigma.js/issues/871#issuecomment-600577941
// And see also here: https://github.com/DefinitelyTyped/DefinitelyTyped/issues/34776
import {SigmaV01} from './js/sigma';
const Sigma = sigma as any;


export class SigmaVisual implements IVisual {
    private stopwords: string[];
    
    //#region CONFIGURATION
    /** Maximum number of nodes shown at a time. */
    private readonly maxNodeCount = 40;
    
    /**
     * Delay in milliseconds to defer visual updates after it has been resized.
     * Performance-relevant. Set to 0 to disable deferred updates.
     * */
    private readonly resizeDelay = 100;
    //#endregion CONFIGURATION
    
    private placeholder: HTMLDivElement;
    private placeholderContent: HTMLElement;
    private outerContainer: HTMLDivElement;
    private legend: HTMLDivElement;
    private sigma: SigmaV01.Sigma;
    
    private readonly hoverFilters = new Set<string>();
    private readonly pinFilters = new Set<string>();
    
    /** Timeout id of the update task. Performance-relevant. See update() method. */
    private updateTimeout: number;
    /**
     * Dimensions of the latest viewport the visual has been rendereed for.
     * Performance-relevant. See update() method. */
    private latestViewport: IViewPort;
    
    //#region PUBLIC PROTOCOL
    public constructor(options: VisualConstructorOptions) {
        console.log("🚀 Loading Sigma Text Graph ...", options, new Date().toLocaleString());
        
        this.stopwords = require('csv-loader!../static/stopwords.csv')
            .map((row: string[]) => row[0]);
        this.stopwords.push("museumbarberini"); // TODO: Hardcoded thus ugly.
        // TODO: It would be nicer to specify this information as an input table, but
        // unfortunately, Power BI does not yet support multiple distinct data view mappings.
        
        this.initializeComponent(options.element);
        
        console.log("✅ Sigma Text Graph was sucessfully loaded!");
        // Power BI does not take any notice when an error occurs during execution.
        // If you don't see this message, you know that something has gone wrong ...
    }
    
    @logExceptions()
    public update(options: VisualUpdateOptions) {
        // Optimized for performance. Add a short delay before blocking the main thread while the
        // user is resizing the view.
        if (!this.resizeDelay || !this.latestViewport || (
            this.latestViewport.width == options.viewport.width
                && this.latestViewport.height == options.viewport.height)
        )
            return this.updateNow(options);
        
        if (this.updateTimeout)
            window.clearTimeout(this.updateTimeout);
        var _this = this;
        this.showPlaceholder("");
        this.updateTimeout = window.setTimeout(() => _this.updateNow(options), this.resizeDelay);
    }
    
    @logExceptions()
    public updateNow(options: VisualUpdateOptions) {
        console.log('👂 Updating Sigma Text Graph ...', options, new Date().toLocaleString());
        
        let dataView: DataView;
        let table: DataViewTable;
        let rows: DataViewTableRow[];
        let hasData = true;
        
        // Check data format
        if (!((dataView = options.dataViews[0]) && (table = dataView.table))) {
            this.showPlaceholder("Start by adding some data");
            hasData = false;
        } else if (!table.columns.some(column => column.roles['text'])) {
            this.showPlaceholder("Start by adding a measure");
            hasData = false;
        } else if (((rows = table.rows)?.length ?? 0) == 0) {
            this.showPlaceholder("The measure is empty");
            hasData = false;
        }
        
        if (!hasData) {
            console.log("❌ Aborting update of Sigma Text Graph, not enough data.");
            return;
        }
        
        this.hidePlaceholder();
        sigmaUtils.clean(this.sigma);
        
        // Build graph
        // TODO: Ideally, we could update the graph differentially. This would require extra
        // effort for dealing with the IDs.
        const textsByCategory = rows.groupBy(
            row => String(row[1]),
            row => String(row[0]).toLowerCase());
        new GraphBuilder()
            .analyze(textsByCategory, word => !this.stopwords.includes(word))
            .generateColors()
            .buildGraph(this.sigma)
            .fillLegend(this.legend);
        
        // Draw graph
        this.pinFilters.clear(); // TODO: Keep old filters as possible
        this.hoverFilters.clear();
        this.applyAllFilters(false);
        this.sigma.startForceAtlas2();
        this.sigma.stopForceAtlas2(); // Disable this line to keep nodes dancing until hovered
        
        this.latestViewport = options.viewport;
        
        console.log("✅ Sigma Visualization was successfully updated");
    }
    //#endregion PUBLIC PROTOCOL
    
    @logExceptions()
    private initializeComponent(parent: HTMLElement) {
        parent.style.position = 'relative';
        
        // Create placeholder (will be displayed until valid data are passed)
        this.placeholder = document.createElement('div');
        this.placeholder.className = 'visual-container';
        this.placeholder.style.justifyContent = 'center';
        this.placeholder.style.alignItems = 'center';
        parent.appendChild(this.placeholder);
        const placeholderChild = document.createElement('center');
        placeholderChild.innerHTML = `<h1>${"¯\\_(ツ)_/¯"}</h1>`;
        this.placeholderContent = document.createElement('p');
        this.placeholder.appendChild(placeholderChild);
        placeholderChild.appendChild(this.placeholderContent);
        
        // Create containers
        this.outerContainer = document.createElement('div');
        this.outerContainer.className = 'visual-container';
        this.outerContainer.style.flexFlow = 'column';
        parent.appendChild(this.outerContainer);
        
        this.legend = document.createElement('div');
        this.legend.style.display = 'flex';
        this.outerContainer.appendChild(this.legend);
        
        const sigmaOuterContainer = document.createElement('div');
        this.outerContainer.appendChild(sigmaOuterContainer);
        sigmaOuterContainer.style.flex = '1 1 auto';
        const sigmaContainer = document.createElement('div');
        sigmaContainer.className = 'sigma-expand';
        sigmaOuterContainer.appendChild(sigmaContainer);
        
        // Create sigma instance
        this.sigma = Sigma.init(sigmaContainer);
        this.sigma.drawingProperties = {
            defaultLabelColor: '#f00',
            defaultLabelSize: 24,
            defaultLabelBGColor: '#eee',
            defaultLabelHoverColor: '#f00',
            labelThreshold: 0,
            drawLabels: true,
            defaultEdgeType: 'curve', // TODO: Does not work
            edgeWeightInfluence: 0,
            minNodeSize: 0.5,
            maxNodeSize: 15,
            minEdgeSize: 0.3,
            maxEdgeSize: 1
        };
        this.sigma.mouseProperties = {
            maxRatio: 4 // max zoom factor
        };
        
        this.sigma
            .bind('overnodes', event => this.enterNodes(event.content))
            .bind('outnodes', event => this.leaveNodes(event.content))
            .bind('downnodes', event => this.clickNodes(event.content));
        this.sigma.activateFishEye();
    }
    
    public applyAllFilters(display = true) {
        return this.applyFilters(
            new Set([
                ...this.pinFilters,
                ...this.hoverFilters
            ]), display);
    }
    
    public applyFilters(filters: Set<string>, display = true) {
        console.log("Current filters:", filters);
        
        if (!filters.size) {
            // Show the full graph
            this.sigma
                .iterEdges(edge => edge.hidden = false)
                .iterNodes(node => node.hidden = false);
        } else {
            // Only show the subgraph of nodes that are adjacent to any node from the filter set
            const _filters = Array.from(filters);
            const neighbors = new Map();
            this.sigma
                .iterEdges(edge => {
                    edge.hidden = false;
                    neighbors.getOrSetDefault(edge.source, () => new Set()).add(edge.target);
                    neighbors.getOrSetDefault(edge.target, () => new Set()).add(edge.source);
                })
                .iterNodes(node => {
                    node.hidden = !_filters.every(filter =>
                        node.id == filter || (
                            neighbors.has(node.id) && neighbors.get(node.id).has(filter)));
                });
        }
        
        // Limit number of visible nodes: Only show the largest ones (for sake of clarity)
        // TODO: Restore filtering by edge weight instead (see log)! It's much more interesting!
        const nodeSizes = [];
        this.sigma.iterNodes(node => {if (!node.hidden) nodeSizes.push(node.size);});
        nodeSizes.sort((a, b) => a - b); // JS way of sorting an array of integers 🙄
        const nodeLimit = nodeSizes.length - this.maxNodeCount;
        const minSize = nodeSizes[nodeLimit];
        
        this.sigma
            .iterNodes(node => {if (!node.hidden)
                node.hidden = node.size < minSize;
            })
            .iterEdges(edge => {if (!edge.hidden)
                edge.hidden = [edge.source, edge.target].every(node =>
                    this.sigma.getNodes(node).hidden);
            });
        
        console.log("Filtered nodes to:", (() => {const nodes = new Set(); this.sigma.iterNodes(
            n => {if (!n.hidden) nodes.add(n.label);}); return nodes;})());
        
        if (display) this.sigma.draw();
    }
    
    //#region EVENTHANDLING
    private enterNodes(nodeIds: string[]) {
        nodeIds.forEach(this.hoverFilters.add, this.hoverFilters);
        this.applyAllFilters();
    }
    
    private leaveNodes(nodeIds: string[]) {
        nodeIds.forEach(this.hoverFilters.delete, this.hoverFilters);
        this.applyAllFilters();
    }
    
    private clickNodes(nodes: string[]) {
        nodes.forEach(nodeId => {
            if (!this.pinFilters.has(nodeId)) {
                this.pinFilters.add(nodeId);
            } else {
                this.pinFilters.delete(nodeId);
                this.hoverFilters.delete(nodeId);
            }
            this.sigma.iterNodes(node => { if (node.id == nodeId) {
                node.forceLabel = this.pinFilters.has(nodeId);
                node.label = node.forceLabel ? node.label.toUpperCase() : node.label.toLowerCase();
            }});
        });
        this.applyAllFilters();
    }
    //#endregion EVENTHANDLING
    
    private showPlaceholder(message: string) {
        this.placeholderContent.innerHTML = message;
        this.placeholder.style.visibility = 'visible';
        this.outerContainer.style.visibility = 'hidden';
    }
    
    private hidePlaceholder() {
        this.placeholder.style.visibility = 'hidden';
        this.outerContainer.style.visibility = 'visible';
    }
}


/** Provides logic for building a text graph from a set of texts. */
class GraphBuilder {
    
    //#region CONFIGURATION
    private readonly nodeSize = 800;
    
    private readonly colorLightCoefficient = 42; // the higher the more nodes can be seen
    private readonly colorSaturationCoefficients = [
        0.1, // the higher the faster nodes get grey
        3 // the higher the more color is in the graph
    ];
    //#endregion CONFIGURATION
    
    private categories: string[];
    private wordsByTextByCategory: Map<string, Map<string, string[]>>;
    /**
     * The key of the following map is a Symbol which contains the JSON representation of an Edge
     * instance. This is the best possibility I found for using custom equality for the map's key
     * comparison.
     */
    private edgeWeights: Map<Symbol, number>;
    private histogram: Map<string, number>;
    private histogramsByCategory: Map<string, Map<string, number>>;
    
    private hues: number[] | null;
    
    /**
     * Stores texts into this instance and performs graph analysis on it. Filter out words that do
     * not match wordFilter.
     */
    public analyze(textsByCategory: Map<string, string[]>, wordFilter: (word: string) => boolean) {
        this.categories = Array.from(textsByCategory.keys());
        this.analyzeTexts(textsByCategory, wordFilter);
        this.analyzeWords();
        return this;
    }
    
    /** Generates different hues for each text category. */
    public generateColors() {
        if (this.categories.length < 2) {
            this.hues = null;
            return this;
        }
        this.hues = this.categories.map((_category, index) =>
            index / this.categories.length * (2 * Math.PI));
        return this;
    }
    
    /** Translates the graph into the given sigma instance. */
    public buildGraph(sigma: SigmaV01.Sigma) {
        const nodeIds = new Map();
        let componentId = 0;
        
        this.histogram.forEach((count, word) => {
            nodeIds.set(word, ++componentId);
            sigma.addNode(componentId, {
                id: componentId,
                label: word,
                
                size: count * this.nodeSize,
                labelSize: count,
                
                color: this.computeColor(word, count),
                
                // TODO: Unused potential here! Find a way to position elements on a useful way.
                x: 100 - 200 * Math.random(),
                y: 100 - 200 * Math.random(),
                
                forceLabel: false,
                hidden: false,
                attributes: []
            });
        });
        
        this.edgeWeights.forEach((weight, edge) => {
            const [word1, word2] = JSON.parse((<any>edge).description);
            sigma.addEdge(++componentId, nodeIds.get(word1), nodeIds.get(word2), {
                id: componentId,
                source: nodeIds.get(word1),
                target: nodeIds.get(word2),
                
                weight: weight,
                
                hidden: false,
                attributes: []
            });
        });
        
        return this;
    }
    
    public fillLegend(legend: HTMLDivElement) {
        legend.style.display = this.hues ? 'flex' : '';
        legend.innerHTML = ''; // remove all children
        if (!this.hues)
            return this;
        this.categories?.forEach((category, index) => {
            const legendItem = document.createElement('div');
            legendItem.className = 'legend-item';
            legendItem.style.background = `hsl(${this.hues[index] / (2 * Math.PI) * 360}, 87%, 79%)`;
            legendItem.innerHTML = category;
            const tooltip = document.createElement('span');
            tooltip.className = 'legend-tooltip';
            tooltip.innerHTML = category;
            legendItem.appendChild(tooltip);
            legend.appendChild(legendItem);
        });
    }
    
    /**
     * Splits all texts from the given map into words, cleans them and filters them by wordFilter.
     */
    private analyzeTexts(
        textsByCategory: Map<string, string[]>,
        wordFilter: (word: string) => boolean)
    {
        this.wordsByTextByCategory = textsByCategory.mapEx(texts =>
            texts.mapEx(text =>
                text
                    .split(/\s+/)
                    .map(word => word.trimEx(/\p{P}/gu))
                    .filter(word => word)
                    .filter(wordFilter)
                    /* Further cleansing ideas:
                     * define custom ignore words/replacements (museumbarberini -> barberini, ...)
                     */
            )
        );
        return this;
    }
    
    /** Performs frequency analysis on all words. Computes edge weights of the text graph. */
    private analyzeWords() {
        const allWords = [...this.wordsByTextByCategory.values()].fold(wordsByText =>
            [...wordsByText.values()].flatten());
        this.histogram = histogram(allWords);
        const allWordsByCategory = this.wordsByTextByCategory.mapEx(wordsByText =>
            [...wordsByText.values()].flatten());
        this.histogramsByCategory = allWordsByCategory.mapEx(histogram);
        
        const edgeWeights = new Map<Symbol, number>();
        this.wordsByTextByCategory.forEach(wordsByText =>
            wordsByText.forEach(words => {
                words.forEach((word1, index1) => words.forEach((word2, index2) => {
                    if (index1 >= index2) return;
                    if (word1 == word2) return;
                    const edge = new UndirectedEdge(word1, word2).key();
                    edgeWeights.update(edge, 0, weight =>
                        weight + (1 / (index2 - index1))); // Weight closer words higher
                }));
            })
        );
        this.edgeWeights = edgeWeights;
        return this;
    }
    
    /**
     * Computes the color for a word based on the associated categories.
     * @param count The number of occurences of the word.
     * */
    private computeColor(word: string, count: number) {
        const saturations = this.categories.map(category =>
            this.histogramsByCategory.get(category).get(word) ?? 0);
        let [hue, sat] = this.hues
            ? mathUtils.deconstructPolar(this.hues
                .zip(saturations, (hue, sat) => math.complex({r: sat, phi: hue}))
                .reduce((sum, next) => <math.Complex>math.add(sum, next), math.complex(0, 0)))
            : [0, 0];
        const light = Math.pow(1 - count, this.colorLightCoefficient);
        sat = Math.pow(sat, this.colorSaturationCoefficients[0]);
        sat /= Math.SQRT2 * this.categories.length;
        sat *= this.colorSaturationCoefficients[1];
        return d3.hsl(hue / (2 * Math.PI) * 360, sat, light).hex();
    }
}


/** Represents an undirected graph's edge that can be used as the key of a Map. */
class UndirectedEdge {
    constructor(node1: string, node2: string) {
        this._nodes = [node1, node2];
        this._nodes.sort();
    }
    
    private _nodes: [string, string];
    
    get nodes() {
        return new Set(this._nodes);
    }
    
    public key(): Symbol {
        return Symbol.for(JSON.stringify(this._nodes));
    }
}
