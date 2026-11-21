import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../dashboard-panel-card.yaml', import.meta.url), 'utf8');
const match = source.match(
	/custom_fields:\s*\r?\n\s+panel:\s*\|\r?\n\s+\[\[\[\r?\n([\s\S]*?)\r?\n\s*\]\]\]/,
);
assert.ok(match, 'the panel-card JS template could not be extracted');

const lines = match[1].replace(/\r\n/g, '\n').split('\n');
const indentation = Math.min(
	...lines.filter(line => line.trim()).map(line => line.match(/^[ ]*/)[0].length),
);
const body = lines.map(line => line.slice(indentation)).join('\n');
const render = new Function('hass', 'variables', body);

const prefix = 'tellybox_tellybox_local';
const sensor = name => `sensor.${prefix}_${name}`;
const binary = name => `binary_sensor.${prefix}_${name}`;

function hassFor(states = {}, attributes = {}) {
	const entities = {};
	for (const [id, state] of Object.entries(states)) {
		entities[id] = {
			state: state === null ? 'unknown' : String(state),
			attributes: attributes[id] || {},
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

test('renders counts, uptime, memory, disk and the 24-hour play count', () => {
	const output = run(
		{
			[binary('online')]: 'on',
			[sensor('active_streams')]: '1',
			[sensor('viewers')]: '2',
			[sensor('paused_streams')]: '1',
			[sensor('measured_remote_upload')]: '25',
			[sensor('configured_upload_limit')]: '50',
			[sensor('service_uptime')]: '93784',
			[sensor('host_uptime')]: '86400',
			[sensor('memory_usage')]: '42.4',
			[sensor('media_disk_available_space')]: '500',
			[sensor('play_requests_24_hours')]: '7',
		},
		{
			[sensor('measured_remote_upload')]: { unit_of_measurement: 'Mbit/s' },
			[sensor('configured_upload_limit')]: { unit_of_measurement: 'Mbit/s' },
			[sensor('service_uptime')]: { unit_of_measurement: 's' },
			[sensor('host_uptime')]: { unit_of_measurement: 's' },
			[sensor('media_disk_available_space')]: { unit_of_measurement: 'GB' },
		},
	);
	assert.match(output, /ONLINE/);
	assert.match(output, /UP 1d 2h/);
	assert.match(output, /<b style="[^"]+">1<\/b><span[^>]*>Watching<\/span>/);
	assert.match(output, /<b style="[^"]+">2<\/b><span[^>]*>Viewers<\/span>/);
	assert.match(output, /<b style="[^"]+">25\.0<\/b><span[^>]*>Mbit\/s up<\/span>/);
	assert.match(output, /<b style="[^"]+">50<\/b><span[^>]*>Mbit\/s cap<\/span>/);
	assert.match(output, /Host up 1d 0h/);
	assert.match(output, /Memory 42%/);
	assert.match(output, /Disk 500\.0 GB free/);
	assert.match(output, /7 plays · 24h/);
	assert.match(output, /width:50%;/);
	assertSafeHtml(output);
});

test('the play count prefers the real 24-hour suffix and keeps a legacy fallback', () => {
	const preferred = run({
		[binary('online')]: 'on',
		[sensor('play_requests_24_hours')]: '8',
		[sensor('plays')]: '99',
	});
	assert.match(preferred, /8 plays · 24h/);
	assert.doesNotMatch(preferred, /99 plays/);

	const legacy = run({ [binary('online')]: 'on', [sensor('plays')]: '5' });
	assert.match(legacy, /5 plays · 24h/);

	const absent = run({ [binary('online')]: 'on' });
	assert.doesNotMatch(absent, /plays/);
});

test('the disk row discovers the available-space sensor and prefers a media disk', () => {
	const media = run({
		[binary('online')]: 'on',
		[sensor('backup_disk_available_space')]: '9',
		[sensor('media_disk_available_space')]: '1.5',
	}, {
		[sensor('backup_disk_available_space')]: { unit_of_measurement: 'GB' },
		[sensor('media_disk_available_space')]: { unit_of_measurement: 'GB' },
	});
	assert.match(media, /Disk 1\.5 GB free/);
	assert.doesNotMatch(media, /9\.0 GB/);

	const any = run({
		[binary('online')]: 'on',
		[sensor('usb_disk_available_space')]: '2',
	}, { [sensor('usb_disk_available_space')]: { unit_of_measurement: 'GB' } });
	assert.match(any, /Disk 2\.0 GB free/);

	// A "Media" label yields _media_available_space rather than _media_disk_available_space.
	const shortLabel = run({
		[binary('online')]: 'on',
		[sensor('media_available_space')]: '3',
	}, { [sensor('media_available_space')]: { unit_of_measurement: 'GB' } });
	assert.match(shortLabel, /Disk 3\.0 GB free/);

	const none = run({ [binary('online')]: 'on' });
	assert.match(none, /Disk — free/);

	const otherInstallation = run({
		[binary('online')]: 'on',
		'sensor.tellybox_office_media_disk_available_space': '4',
	});
	assert.match(otherInstallation, /Disk — free/);
});

test('offline wins over a last-seen maintenance flag', () => {
	const offline = run({
		[binary('online')]: 'off',
		[binary('maintenance_mode')]: 'on',
	});
	assert.match(offline, /OFFLINE/);
	assert.doesNotMatch(offline, /MAINTENANCE/);
	assert.match(offline, /Telemetry paused/);

	const maintenance = run({
		[binary('online')]: 'on',
		[binary('maintenance_mode')]: 'on',
	});
	assert.match(maintenance, /MAINTENANCE/);
	assert.match(maintenance, /Maintenance mode — playback blocked/);

	const stale = run({
		[binary('online')]: 'on',
		[binary('maintenance_mode')]: 'unavailable',
	});
	assert.match(stale, /ONLINE/);
	assert.doesNotMatch(stale, /MAINTENANCE/);

	const unknown = run({ [binary('maintenance_mode')]: 'on' });
	assert.match(unknown, /UNKNOWN/);
	assert.doesNotMatch(unknown, /MAINTENANCE/);
});

test('memory prefers the memory_usage sensor and falls back to total and available', () => {
	const usage = run({
		[binary('online')]: 'on',
		[sensor('memory_usage')]: '37.4',
		[sensor('memory_total')]: '100',
		[sensor('memory_available')]: '50',
	});
	assert.match(usage, /Memory 37%/);

	const derived = run({
		[binary('online')]: 'on',
		[sensor('memory_total')]: '100',
		[sensor('memory_available')]: '40',
	});
	assert.match(derived, /Memory 60%/);

	const invalidUsage = run({
		[binary('online')]: 'on',
		[sensor('memory_usage')]: 'n/a',
		[sensor('memory_total')]: '100',
		[sensor('memory_available')]: '40',
	});
	assert.match(invalidUsage, /Memory 60%/);

	const incomplete = run({
		[binary('online')]: 'on',
		[sensor('memory_total')]: '100',
	});
	assert.match(incomplete, /Memory —/);
	assert.doesNotMatch(incomplete, /NaN|Infinity/);
});
