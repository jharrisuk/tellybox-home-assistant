import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../dashboard-button-card.yaml', import.meta.url), 'utf8');
const match = source.match(
	/custom_fields:\s*\r?\n\s+panel:\s*\|\r?\n\s+\[\[\[\r?\n([\s\S]*?)\r?\n\s*\]\]\]/,
);
assert.ok(match, 'the button-card JS template could not be extracted');

const lines = match[1].replace(/\r\n/g, '\n').split('\n');
const indentation = Math.min(
	...lines.filter(line => line.trim()).map(line => line.match(/^[ ]*/)[0].length),
);
const body = lines.map(line => line.slice(indentation)).join('\n');
const render = new Function('hass', 'variables', body);

const prefix = 'tellybox_tellybox_local';
const suffixes = {
	active: 'active_streams',
	connected: 'connected_streams',
	local: 'local_streams',
	remote: 'remote_streams',
	downloads: 'active_downloads',
	measured: 'measured_remote_upload',
	cap: 'configured_upload_limit',
	uptime: 'service_uptime',
};

function hassFor(states = {}, attributes = {}) {
	const entities = {};
	for (const [suffix, state] of Object.entries(states)) {
		const domain = suffix === 'online' ? 'binary_sensor' : 'sensor';
		const id = `${domain}.${prefix}_${suffixes[suffix] || suffix}`;
		entities[id] = {
			state: state === null ? 'unknown' : String(state),
			attributes: attributes[suffix] || {},
		};
	}
	return { states: entities };
}

function run(states, attributes = {}, variables = {}) {
	return render(hassFor(states, attributes), {
		entity_prefix: prefix,
		logo: '/local/tellybox/dark_logo.png',
		...variables,
	});
}

function assertSafeHtml(output) {
	assert.doesNotMatch(output, /NaN|Infinity|undefined|null/);
	assert.doesNotMatch(output, /<script/i);
	assert.doesNotMatch(output, /\sonerror\s*=\s*["']/i);
}

test('renders the supplied panel with counts, upload, cap and uptime', () => {
	const output = run(
		{
			online: 'on',
			active: '1',
			connected: '2',
			local: '1',
			remote: '1',
			downloads: '0',
			measured: '25',
			cap: '50',
			uptime: '93784',
		},
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.match(output, /ONLINE/);
	assert.match(output, /UP 1d 2h/);
	assert.match(output, /<b style="[^"]+">1<\/b><span[^>]*>Watching<\/span>/);
	assert.match(output, /<b style="[^"]+">25\.0<\/b><span[^>]*>Mbit\/s up<\/span>/);
	assert.match(output, /<b style="[^"]+">50<\/b><span[^>]*>Mbit\/s cap<\/span>/);
	assert.match(output, /<b style="[^"]+">2<\/b><span[^>]*>Connected<\/span>/);
	assert.match(output, /<b style="[^"]+">0<\/b><span[^>]*>Downloads<\/span>/);
	assert.match(output, /width:50%;/);
	assert.match(output, /50% of 50 Mbit\/s cap/);
	assert.match(output, /src="\/local\/tellybox\/dark_logo\.png"/);
	assertSafeHtml(output);
});

test('missing and invalid values stay unknown and never become zero', () => {
	const output = run(
		{
			online: 'unavailable',
			active: 'unknown',
			connected: '',
			local: 'NaN',
			remote: '<script>alert(1)</script>',
			measured: 'n/a',
			cap: 'NaN',
			uptime: 'unknown',
		},
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 'fortnight' },
		},
	);
	assert.match(output, /UNKNOWN/);
	assert.match(output, /Telemetry unavailable/);
	assert.match(output, /UP —/);
	assert.ok(output.includes('>—</b>'), 'missing values must render as a dash');
	assert.doesNotMatch(output, />0<\/b>/);
	assert.doesNotMatch(output, /<script/i);
	assertSafeHtml(output);
});

test('a zero upload cap is unlimited and cannot divide by zero', () => {
	const output = run(
		{
			online: 'on',
			active: '0',
			connected: '1',
			local: '1',
			remote: '0',
			downloads: '0',
			measured: '5',
			cap: '0',
			uptime: '0',
		},
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.match(output, />∞<\/b>/);
	assert.match(output, /Unlimited cap/);
	assert.match(output, /Unlimited upload cap/);
	assert.match(output, /width:0%;/);
	assert.match(output, /UP 0s/);
	assert.doesNotMatch(output, /NaN|Infinity/);
});

test('negative or absent cap is unavailable rather than unlimited', () => {
	const negative = run(
		{ online: 'on', active: '0', measured: '5', cap: '-5', uptime: '60' },
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.match(negative, /Upload rate unavailable|cap unavailable/i);
	assert.doesNotMatch(negative, />∞<\/b>/);
	assert.doesNotMatch(negative, /NaN|Infinity/);

	const missing = run(
		{ online: 'on', active: '0', measured: '5', uptime: '60' },
		{ measured: { unit_of_measurement: 'Mbit/s' }, uptime: { unit_of_measurement: 's' } },
	);
	assert.match(missing, /Upload cap unavailable/);
	assert.doesNotMatch(missing, /NaN|Infinity/);
});

test('injected units, logo and invalid uptime are escaped or discarded', () => {
	const output = run(
		{
			online: 'on',
			active: '1',
			measured: '1',
			cap: '1',
			uptime: '<img src=x onerror=alert(1)>',
		},
		{
			measured: { unit_of_measurement: 'Mbit/s"><img src=x onerror=alert(1)>' },
			cap: { unit_of_measurement: 'Mbit/s"><img src=x onerror=alert(1)>' },
			uptime: { unit_of_measurement: 's' },
		},
		{ logo: 'x" onerror="alert(1)' },
	);
	assert.doesNotMatch(output, /<img src=x/);
	assert.doesNotMatch(output, /onerror="alert/);
	assert.match(output, /&lt;img src=x onerror=alert\(1\)&gt;/);
	assert.match(output, /src="x&quot; onerror=&quot;alert\(1\)"/);
	assert.match(output, /UP —/);
	assertSafeHtml(output);
});

test('uptime respects each supported unit and rejects an unknown one', () => {
	const cases = [
		['ms', '3600000', '1h 0m'],
		['s', '3600', '1h 0m'],
		['min', '60', '1h 0m'],
		['h', '1', '1h 0m'],
		['d', '1', '1d 0h'],
		['w', '1', '7d 0h'],
	];
	for (const [unit, state, expected] of cases) {
		const output = run(
			{ online: 'on', active: '0', uptime: state },
			{ uptime: { unit_of_measurement: unit } },
		);
		assert.match(output, new RegExp(`UP ${expected}`), unit);
	}
	const unknown = run(
		{ online: 'on', active: '0', uptime: '12' },
		{ uptime: { unit_of_measurement: 'fortnight' } },
	);
	assert.match(unknown, /UP —/);
});

test('offline status pauses telemetry and still shows a safe meter', () => {
	const output = run(
		{ online: 'off', active: '0', measured: '10', cap: '50', uptime: '60' },
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.match(output, /OFFLINE/);
	assert.match(output, /Server offline - telemetry paused/);
	assert.match(output, /width:0%;/);
	assert.doesNotMatch(output, /NaN|Infinity/);
});

test('a missing hass object still renders an unknown, safe panel', () => {
	const output = render(undefined, {});
	assert.match(output, /UNKNOWN/);
	assert.match(output, /Telemetry unavailable/);
	assert.ok(output.includes('>—</b>'));
	assert.doesNotMatch(output, /NaN|Infinity|undefined/);
});

test('a real zero stays zero and a zero rate is a real zero percent', () => {
	const output = run(
		{
			online: 'on',
			active: '0',
			connected: '0',
			local: '0',
			remote: '0',
			downloads: '0',
			measured: '0',
			cap: '50',
			uptime: '0',
		},
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.match(output, /<b style="[^"]+">0<\/b><span[^>]*>Watching<\/span>/);
	assert.match(output, /<b style="[^"]+">0<\/b><span[^>]*>Downloads<\/span>/);
	assert.match(output, /<b style="[^"]+">0\.0<\/b><span[^>]*>Mbit\/s up<\/span>/);
	assert.match(output, /0% of 50 Mbit\/s cap/);
	assert.match(output, /UP 0s/);
	assert.doesNotMatch(output, /NaN|Infinity/);
});

test('a negative uptime is unknown rather than a wrapped duration', () => {
	const output = run(
		{ online: 'on', active: '0', uptime: '-60' },
		{ uptime: { unit_of_measurement: 's' } },
	);
	assert.match(output, /UP —/);
	assert.doesNotMatch(output, /NaN|Infinity/);
});

test('negative counters and upload rates stay unknown', () => {
	const output = run(
		{ online: 'on', active: '-1', measured: '-5', cap: '50', uptime: '60' },
		{
			measured: { unit_of_measurement: 'Mbit/s' },
			cap: { unit_of_measurement: 'Mbit/s' },
			uptime: { unit_of_measurement: 's' },
		},
	);
	assert.doesNotMatch(output, />-1<\/b>/);
	assert.doesNotMatch(output, />-5\.0<\/b>/);
	assert.match(output, /Upload rate unavailable/);
	assert.match(output, /width:0%;/);
	assert.doesNotMatch(output, /NaN|Infinity/);
});

test('an empty logo value falls back to a text wordmark', () => {
	const output = run(
		{ online: 'on', active: '0', uptime: '60' },
		{ uptime: { unit_of_measurement: 's' } },
		{ logo: '' },
	);
	assert.doesNotMatch(output, /<img /);
	assert.match(output, />Tellybox<\/span>/);
});

test('the entity prefix can be changed in one place', () => {
	const custom = 'tellybox_office';
	const entities = {
		states: {
			[`binary_sensor.${custom}_online`]: { state: 'on', attributes: {} },
			[`sensor.${custom}_active_streams`]: { state: '2', attributes: {} },
			[`sensor.${custom}_service_uptime`]: {
				state: '60',
				attributes: { unit_of_measurement: 's' },
			},
		},
	};
	const output = render(entities, {
		entity_prefix: custom,
		logo: '/local/tellybox/dark_logo.png',
	});
	assert.match(output, /ONLINE/);
	assert.match(output, /<b style="[^"]+">2<\/b><span[^>]*>Watching<\/span>/);
	assert.match(output, /UP 1m/);
	assertSafeHtml(output);
});
