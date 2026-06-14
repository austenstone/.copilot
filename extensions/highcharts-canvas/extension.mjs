import http from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";

import { CanvasError, createCanvas, joinSession } from "@github/copilot-sdk/extension";

const __dirname = dirname(fileURLToPath(import.meta.url));

// instanceId → { server, url, state, subscribers }
const instances = new Map();

const DEFAULT_STATE = () => ({ kind: "chart", options: null, mapData: null, title: "", updatedAt: null });

function broadcast(entry) {
	const payload = `data: ${JSON.stringify(entry.state)}\n\n`;
	for (const res of entry.subscribers) res.write(payload);
}

async function startServer() {
	const state = DEFAULT_STATE();
	const subscribers = new Set();
	const entry = { state, subscribers, server: null, url: null };

	const server = http.createServer(async (req, res) => {
		try {
			if (req.method === "GET" && (req.url === "/" || req.url === "/index.html")) {
				const html = await readFile(join(__dirname, "index.html"));
				res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
				res.end(html);
				return;
			}
			if (req.method === "GET" && req.url === "/events") {
				res.writeHead(200, {
					"Content-Type": "text/event-stream",
					"Cache-Control": "no-cache",
					Connection: "keep-alive",
				});
				res.write(`data: ${JSON.stringify(state)}\n\n`);
				subscribers.add(res);
				req.on("close", () => subscribers.delete(res));
				return;
			}
			res.writeHead(404);
			res.end();
		} catch (err) {
			res.writeHead(500, { "Content-Type": "application/json" });
			res.end(JSON.stringify({ error: err instanceof Error ? err.message : String(err) }));
		}
	});

	await new Promise((r) => server.listen(0, "127.0.0.1", r));
	const { port } = server.address();
	entry.server = server;
	entry.url = `http://127.0.0.1:${port}/`;
	return entry;
}

function getEntry(instanceId) {
	const entry = instances.get(instanceId);
	if (!entry) {
		throw new CanvasError(
			"canvas_instance_not_found",
			`No open canvas for instanceId=${instanceId}. Call open_canvas first.`,
		);
	}
	return entry;
}

function setChart(instanceId, kind, options, extras = {}) {
	const entry = getEntry(instanceId);
	if (!options || typeof options !== "object") {
		throw new CanvasError("canvas_input_invalid", "`options` must be a Highcharts options object.");
	}
	entry.state.kind = kind;
	entry.state.options = options;
	entry.state.title = options?.title?.text ?? extras.title ?? "";
	entry.state.mapData = extras.mapData ?? null;
	entry.state.updatedAt = Date.now();
	broadcast(entry);
	return { status: `Rendered ${kind} chart`, title: entry.state.title };
}

const optionsSchema = {
	type: "object",
	properties: {
		options: { type: "object", description: "Highcharts options object (see https://api.highcharts.com/highcharts/)." },
	},
	required: ["options"],
};

const mapSchema = {
	type: "object",
	properties: {
		options: { type: "object", description: "Highmaps options object." },
		mapData: { type: "string", description: "Map URL or stringified topojson." },
	},
	required: ["options"],
};

const chartCanvas = createCanvas({
	id: "chart",
	displayName: "Highcharts",
	description:
		"Render interactive Highcharts charts inline. Supports basic charts, stock, dashboards, maps, gantt, and standalone data grids. Pass a full Highcharts options object to any action.",
	actions: [
		{ name: "render_chart", description: "Render any standard Highcharts chart.", inputSchema: optionsSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "chart", input.options) },
		{ name: "render_stock_chart", description: "Render a Highcharts Stock financial chart.", inputSchema: optionsSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "stock", input.options) },
		{ name: "render_dashboard", description: "Render a Highcharts Dashboards layout.", inputSchema: optionsSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "dashboard", input.options) },
		{ name: "render_map", description: "Render a Highcharts Maps chart.", inputSchema: mapSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "map", input.options, { mapData: input.mapData }) },
		{ name: "render_gantt", description: "Render a Highcharts Gantt chart.", inputSchema: optionsSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "gantt", input.options) },
		{ name: "render_grid", description: "Render a standalone Highcharts Grid.", inputSchema: optionsSchema,
			handler: ({ instanceId, input }) => setChart(instanceId, "grid", input.options) },
	],
	open: async ({ instanceId, input }) => {
		let entry = instances.get(instanceId);
		if (!entry) {
			entry = await startServer();
			instances.set(instanceId, entry);
		}
		if (input && typeof input === "object" && input.options) {
			setChart(instanceId, input.kind ?? "chart", input.options, { mapData: input.mapData, title: input.title });
		}
		return {
			url: entry.url,
			title: entry.state.title || "Highcharts",
			status: entry.state.options ? `Showing ${entry.state.kind}` : "Waiting for data",
		};
	},
	onClose: async ({ instanceId }) => {
		const entry = instances.get(instanceId);
		if (!entry) return;
		instances.delete(instanceId);
		for (const res of entry.subscribers) { try { res.end(); } catch {} }
		await new Promise((r) => entry.server.close(() => r()));
	},
});

await joinSession({ canvases: [chartCanvas] });
