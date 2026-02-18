"""Service for extracting GPX data from nakarte.me."""

import html
import re
from typing import Optional

from playwright.async_api import (
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
from structlog import BoundLogger

from src.utils.logger import get_logger


class NakarteService:
    """Service for downloading GPX tracks from nakarte.me."""

    NAKARTE_URL_PATTERN = re.compile(
        r"^https?://(?:www\.)?nakarte\.me/#.*nktl=([A-Za-z0-9_-]+).*$"
    )

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        logger: Optional[BoundLogger] = None,
    ):
        """
        Initialize Nakarte service.

        Args:
            headless: Run browser in headless mode
            timeout: Browser timeout in milliseconds
            logger: Logger instance
        """
        self.headless = headless
        self.timeout = timeout
        self.logger = logger or get_logger(__name__)
        self._browser: Optional[Browser] = None
        self._playwright = None

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate nakarte.me URL format.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid, False otherwise
        """
        return bool(NakarteService.NAKARTE_URL_PATTERN.match(url))

    @staticmethod
    def extract_track_id(url: str) -> Optional[str]:
        """
        Extract track identifier from nakarte.me URL.

        Args:
            url: nakarte.me URL

        Returns:
            Track identifier or None if not found
        """
        match = NakarteService.NAKARTE_URL_PATTERN.match(url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _normalize_track_name(name: Optional[str], track_id: Optional[str]) -> str:
        """Normalize track name for XML/filename usage."""
        value = html.unescape((name or "").strip())
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"\.(gpx|kml|geojson)\s*$", "", value, flags=re.IGNORECASE)
        value = value.strip(" .-_")

        if not value:
            short_id = (track_id or "track")[:8]
            value = f"Nakarte track {short_id}"

        return value

    def extract_track_name_from_gpx(self, gpx_data: bytes | str, track_id: Optional[str] = None) -> str:
        """Extract and normalize track name from GPX content."""
        if isinstance(gpx_data, bytes):
            text = gpx_data.decode("utf-8", errors="ignore")
        else:
            text = gpx_data

        match = re.search(r"<trk>\s*<name>(.*?)</name>", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            match = re.search(r"<name>(.*?)</name>", text, flags=re.IGNORECASE | re.DOTALL)

        raw_name = match.group(1).strip() if match else None
        return self._normalize_track_name(raw_name, track_id)

    def ensure_friendly_track_name(self, gpx_data: bytes | str, track_id: Optional[str] = None) -> bytes:
        """Ensure GPX contains a friendly <trk><name> value."""
        if isinstance(gpx_data, bytes):
            text = gpx_data.decode("utf-8", errors="ignore")
        else:
            text = gpx_data

        friendly_name = self.extract_track_name_from_gpx(text, track_id)
        escaped_name = html.escape(friendly_name, quote=False)

        if re.search(r"<trk>\s*<name>.*?</name>", text, flags=re.IGNORECASE | re.DOTALL):
            text = re.sub(
                r"(<trk>\s*<name>).*?(</name>)",
                lambda m: f"{m.group(1)}{escaped_name}{m.group(2)}",
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        elif re.search(r"<trk>", text, flags=re.IGNORECASE):
            text = re.sub(
                r"(<trk>)",
                lambda m: f"{m.group(1)}\n    <name>{escaped_name}</name>",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

        return text.encode("utf-8")

    def build_filename_from_gpx(self, gpx_data: bytes | str, track_id: Optional[str] = None) -> str:
        """Build a safe, friendly GPX filename from track metadata."""
        friendly_name = self.extract_track_name_from_gpx(gpx_data, track_id)
        safe_name = re.sub(r'[\\/:*?"<>|]+', " ", friendly_name)
        safe_name = re.sub(r"\s+", " ", safe_name).strip(" .")
        if not safe_name:
            short_id = (track_id or "track")[:8]
            safe_name = f"Nakarte track {short_id}"
        return f"{safe_name}.gpx"

    async def _get_browser(self) -> Browser:
        """Get or create browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self.logger.info("browser_launched", headless=self.headless)
        return self._browser

    async def download_gpx(self, url: str) -> bytes:
        """
        Download GPX track from nakarte.me URL.

        Args:
            url: nakarte.me URL

        Returns:
            GPX file content as bytes

        Raises:
            ValueError: If URL is invalid
            RuntimeError: If GPX download fails
        """
        if not self.validate_url(url):
            self.logger.error("invalid_url", url=url)
            raise ValueError(f"Invalid nakarte.me URL: {url}")

        track_id = self.extract_track_id(url)
        self.logger.info("downloading_gpx", url=url, track_id=track_id)

        browser = await self._get_browser()
        page: Optional[Page] = None

        try:
            page = await browser.new_page()

            self.logger.info("navigating_to_url", url=url)
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)

            self.logger.info("waiting_for_app_initialization")
            await page.wait_for_timeout(12000)

            page_debug = await page.evaluate(
                """
                () => {
                    return {
                        hasWindow: typeof window !== 'undefined',
                        hasApp: !!window.app,
                        appKeys: window.app ? Object.keys(window.app).slice(0, 10) : [],
                        hasWebpackChunk: typeof window.webpackChunknakarte !== 'undefined'
                    };
                }
                """
            )
            self.logger.info("page_debug", **page_debug)

            gpx_data = await page.evaluate(
                """
                async (trackId) => {
                    const toNumber = (value) => {
                        const n = Number(value);
                        return Number.isFinite(n) ? n : null;
                    };

                    const xmlEscape = (s) => String(s)
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&apos;');

                    const pointFromUnknown = (raw) => {
                        if (!raw) return null;

                        if (Array.isArray(raw) && raw.length >= 2) {
                            const lat = toNumber(raw[0]);
                            const lon = toNumber(raw[1]);
                            const ele = raw.length >= 3 ? toNumber(raw[2]) : null;
                            if (lat === null || lon === null) return null;
                            return { lat, lon, ele };
                        }

                        if (typeof raw === 'object') {
                            const lat = toNumber(raw.lat ?? raw.latitude ?? raw[0]);
                            const lon = toNumber(raw.lng ?? raw.lon ?? raw.longitude ?? raw[1]);
                            const ele = toNumber(raw.alt ?? raw.ele ?? raw.elevation ?? raw[2]);
                            if (lat === null || lon === null) return null;
                            return { lat, lon, ele };
                        }

                        return null;
                    };

                    const pointsFromUnknown = (container) => {
                        if (!container || !Array.isArray(container)) return [];
                        const points = [];
                        for (const item of container) {
                            if (Array.isArray(item) && item.length > 0 && !pointFromUnknown(item)) {
                                for (const nested of item) {
                                    const p = pointFromUnknown(nested);
                                    if (p) points.push(p);
                                }
                            } else {
                                const p = pointFromUnknown(item);
                                if (p) points.push(p);
                            }
                        }
                        return points;
                    };

                    const normalizeTrackSegments = (track) => {
                        if (track && typeof track.getTrackPolylines === 'function') {
                            const polylines = track.getTrackPolylines() || [];
                            const segments = [];
                            for (const pl of polylines) {
                                if (pl && typeof pl.getLatLngs === 'function') {
                                    const seg = pointsFromUnknown(pl.getLatLngs() || []);
                                    if (seg.length) segments.push(seg);
                                }
                            }
                            if (segments.length) return segments;
                        }

                        const fromSegments = pointsFromUnknown(track?.segments || []);
                        if (fromSegments.length) return [fromSegments];

                        const fromPoints = pointsFromUnknown(track?.points || []);
                        if (fromPoints.length) return [fromPoints];

                        const fromData = pointsFromUnknown(track?.data || []);
                        if (fromData.length) return [fromData];

                        return [];
                    };

                    const buildGpx = (tracksData) => {
                        const now = new Date().toISOString();

                        let gpx = '<?xml version="1.0" encoding="UTF-8"?>\\n';
                        gpx += '<gpx version="1.1" creator="nakarte.me" ';
                        gpx += 'xmlns="http://www.topografix.com/GPX/1/1" ';
                        gpx += 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ';
                        gpx += 'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 ';
                        gpx += 'http://www.topografix.com/GPX/1/1/gpx.xsd">\\n';
                        gpx += `  <metadata>\\n    <time>${now}</time>\\n  </metadata>\\n`;

                        for (const track of tracksData) {
                            const name = xmlEscape(track?.name || 'Track');
                            gpx += `  <trk>\\n    <name>${name}</name>\\n`;
                            for (const segment of (track?.segments || [])) {
                                gpx += '    <trkseg>\\n';
                                for (const p of segment) {
                                    gpx += `      <trkpt lat="${p.lat}" lon="${p.lon}">\\n`;
                                    if (p.ele !== null) {
                                        gpx += `        <ele>${p.ele}</ele>\\n`;
                                    }
                                    gpx += '      </trkpt>\\n';
                                }
                                gpx += '    </trkseg>\\n';
                            }
                            gpx += '  </trk>\\n';
                        }
                        gpx += '</gpx>';
                        return gpx;
                    };

                    const looksLikeTrack = (obj) => {
                        if (!obj || typeof obj !== 'object') return false;
                        return (
                            typeof obj.getTrackPolylines === 'function' ||
                            Array.isArray(obj.segments) ||
                            Array.isArray(obj.points) ||
                            Array.isArray(obj.data)
                        );
                    };

                    const looksLikeTrackManager = (obj) => {
                        if (!obj || typeof obj !== 'object') return false;
                        if (!Array.isArray(obj.tracks)) return false;
                        if (obj.tracks.length === 0) return true;
                        return looksLikeTrack(obj.tracks[0]);
                    };

                    const looksLikeTrackList = (obj) => {
                        if (!obj || typeof obj !== 'object') return false;
                        return (
                            typeof obj.exportTrackAsFile === 'function' &&
                            typeof obj.getTrackPolylines === 'function' &&
                            typeof obj.getTrackPoints === 'function' &&
                            typeof obj.tracks === 'function'
                        );
                    };

                    const looksLikeNakarteUrlLoader = (obj) => {
                        if (!obj) return false;
                        const proto = obj.prototype || obj;
                        return (
                            typeof obj === 'function' &&
                            typeof proto.geoData === 'function' &&
                            typeof proto.paramNames === 'function'
                        );
                    };

                    const findInObjectGraph = (root, predicate, maxNodes = 25000) => {
                        if (!root || typeof root !== 'object') return null;

                        const seen = new WeakSet();
                        const queue = [root];
                        let visited = 0;

                        while (queue.length > 0 && visited < maxNodes) {
                            const cur = queue.shift();
                            if (!cur || typeof cur !== 'object') continue;
                            if (seen.has(cur)) continue;
                            seen.add(cur);
                            visited += 1;

                            try {
                                if (predicate(cur)) return cur;
                            } catch (_) {}

                            let keys = [];
                            try {
                                keys = Object.keys(cur);
                            } catch (_) {}

                            for (const key of keys) {
                                let val;
                                try {
                                    val = cur[key];
                                } catch (_) {
                                    continue;
                                }
                                if (val && typeof val === 'object') {
                                    queue.push(val);
                                }
                            }
                        }

                        return null;
                    };

                    const getWebpackRequire = () => {
                        if (!Array.isArray(window.webpackChunknakarte)) return null;
                        let req = null;
                        try {
                            window.webpackChunknakarte.push([
                                [Symbol('nakarte-gpx-probe')],
                                {},
                                (runtimeRequire) => {
                                    req = runtimeRequire;
                                },
                            ]);
                        } catch (_) {
                            return null;
                        }
                        return req;
                    };

                    const iterWebpackExports = (req, knownIds = [], sourceHints = []) => {
                        const out = [];
                        const seen = new Set();

                        const pushExport = (exp) => {
                            if (!exp || seen.has(exp)) return;
                            seen.add(exp);
                            out.push(exp);
                        };

                        if (req?.c) {
                            for (const entry of Object.values(req.c)) {
                                if (entry?.exports) {
                                    pushExport(entry.exports);
                                    if (entry.exports.default) pushExport(entry.exports.default);
                                }
                            }
                        }

                        const tryRequireById = (id) => {
                            try {
                                const exp = req(id);
                                pushExport(exp);
                                if (exp?.default) pushExport(exp.default);
                            } catch (_) {}
                        };

                        for (const id of knownIds) {
                            tryRequireById(id);
                        }

                        if (req?.m && sourceHints.length > 0) {
                            for (const [id, factory] of Object.entries(req.m)) {
                                let src = '';
                                try {
                                    src = String(factory);
                                } catch (_) {
                                    continue;
                                }

                                if (!sourceHints.some((hint) => src.includes(hint))) {
                                    continue;
                                }

                                tryRequireById(id);
                            }
                        }

                        return out;
                    };

                    const findTrackManager = () => {
                        const directCandidates = [
                            window.app?.trackManager,
                            window.nakarte?.app?.trackManager,
                            window.__nakarte__?.app?.trackManager,
                        ];

                        for (const candidate of directCandidates) {
                            if (looksLikeTrackManager(candidate)) return candidate;
                        }

                        const req = getWebpackRequire();
                        if (!req) return null;
                        const exportsList = iterWebpackExports(
                            req,
                            [28996, 60594],
                            ['TrackList', 'loadTrackFromParam', 'tracks()']
                        );

                        for (const exp of exportsList) {
                            if (looksLikeTrackManager(exp)) return exp;
                            const found = findInObjectGraph(exp, looksLikeTrackManager, 5000);
                            if (found) return found;
                        }

                        return null;
                    };

                    const findTrackFallback = () => {
                        const req = getWebpackRequire();
                        if (!req) return null;
                        const exportsList = iterWebpackExports(
                            req,
                            [28996, 78819, 60594],
                            ['getTrackPolylines', 'saveGpx', 'tracks']
                        );

                        for (const exp of exportsList) {
                            if (looksLikeTrack(exp)) return exp;
                            const found = findInObjectGraph(exp, looksLikeTrack, 5000);
                            if (found) return found;
                        }

                        return null;
                    };

                    const findNakarteUrlLoader = () => {
                        const req = getWebpackRequire();
                        if (!req) return null;
                        const exportsList = iterWebpackExports(
                            req,
                            [12733],
                            ['NakarteUrlLoader', 'loadFromTextEncodedTrackId', 'paramNames']
                        );

                        for (const exp of exportsList) {
                            if (looksLikeNakarteUrlLoader(exp?.NakarteUrlLoader)) {
                                return exp.NakarteUrlLoader;
                            }
                            if (looksLikeNakarteUrlLoader(exp?.default?.NakarteUrlLoader)) {
                                return exp.default.NakarteUrlLoader;
                            }
                            if (looksLikeNakarteUrlLoader(exp)) {
                                return exp;
                            }
                        }

                        return null;
                    };

                    const findNktkParser = () => {
                        const req = getWebpackRequire();
                        if (!req) return null;
                        const exportsList = iterWebpackExports(
                            req,
                            [27142],
                            ['parseNktkSequence', 'parseNktkFragment']
                        );

                        for (const exp of exportsList) {
                            if (typeof exp?.parseNktkSequence === 'function') {
                                return exp;
                            }
                            if (typeof exp?.default?.parseNktkSequence === 'function') {
                                return exp.default;
                            }
                        }

                        return null;
                    };

                    const extractTracksFromGeoData = (geoDataArray) => {
                        if (!Array.isArray(geoDataArray)) {
                            geoDataArray = geoDataArray ? [geoDataArray] : [];
                        }

                        const out = [];
                        for (const item of geoDataArray) {
                            const tracks = item?.tracks;
                            if (!Array.isArray(tracks) || !tracks.length) continue;

                            const segments = [];
                            for (const seg of tracks) {
                                const points = pointsFromUnknown(seg);
                                if (points.length) segments.push(points);
                            }

                            if (segments.length) {
                                out.push({
                                    name: item?.name || 'Track',
                                    segments,
                                });
                            }
                        }

                        return out;
                    };

                    const findTrackList = () => {
                        const directCandidates = [
                            window.trackList,
                            window.app?.trackList,
                            window.nakarte?.trackList,
                            window.nakarte?.app?.trackList,
                            window.__nakarte__?.trackList,
                        ];

                        for (const candidate of directCandidates) {
                            if (looksLikeTrackList(candidate)) return candidate;
                        }

                        if (window.L && window.L._leaflet_id) {
                            const fromWindowGraph = findInObjectGraph(window, looksLikeTrackList, 8000);
                            if (fromWindowGraph) return fromWindowGraph;
                        }

                        const req = getWebpackRequire();
                        if (!req) return null;
                        const exportsList = iterWebpackExports(
                            req,
                            [28996, 60594],
                            ['exportTrackAsFile', 'getTrackPolylines', 'loadTrackFromParam']
                        );

                        for (const exp of exportsList) {
                            if (looksLikeTrackList(exp)) return exp;
                            const found = findInObjectGraph(exp, looksLikeTrackList, 10000);
                            if (found) return found;
                        }

                        return null;
                    };

                    const trackToSegmentsFromExport = (segments) => {
                        const out = [];
                        if (!Array.isArray(segments)) return out;
                        for (const segment of segments) {
                            if (!Array.isArray(segment)) continue;
                            const pts = [];
                            for (const p of segment) {
                                const pp = pointFromUnknown(p);
                                if (pp) pts.push(pp);
                            }
                            if (pts.length) out.push(pts);
                        }
                        return out;
                    };

                    const readTrackListTracks = (trackList) => {
                        if (!trackList || typeof trackList.tracks !== 'function') return [];
                        try {
                            const tracks = trackList.tracks();
                            return Array.isArray(tracks) ? tracks : [];
                        } catch (_) {
                            return [];
                        }
                    };

                    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

                    const binaryStringFromArrayBuffer = (buf) => {
                        const bytes = new Uint8Array(buf);
                        const chunk = 0x8000;
                        let out = '';
                        for (let i = 0; i < bytes.length; i += chunk) {
                            const slice = bytes.subarray(i, Math.min(i + chunk, bytes.length));
                            out += String.fromCharCode(...slice);
                        }
                        return out;
                    };

                    const waitFor = (condition, timeout = 15000) => {
                        return new Promise((resolve, reject) => {
                            const startTime = Date.now();
                            const check = () => {
                                if (condition()) {
                                    resolve();
                                } else if (Date.now() - startTime > timeout) {
                                    reject(new Error('Timeout waiting for condition'));
                                } else {
                                    setTimeout(check, 100);
                                }
                            };
                            check();
                        });
                    };

                    await waitFor(
                        () => !!window.app?.trackManager || !!window.webpackChunknakarte,
                        20000
                    );

                    const debugInfo = {
                        hasWebpackChunk: !!window.webpackChunknakarte,
                        loaderFound: false,
                        parserFound: false,
                        trackListFound: false,
                        trackManagerFound: false,
                    };

                    if (trackId) {
                        const LoaderClass = findNakarteUrlLoader();
                        debugInfo.loaderFound = !!LoaderClass;
                        if (LoaderClass) {
                            try {
                                const loader = new LoaderClass();
                                const geodata = await loader.geoData('nktl', trackId);
                                const parsedTracks = extractTracksFromGeoData(geodata);
                                if (parsedTracks.length) {
                                    return {
                                        source: 'loader',
                                        gpx: buildGpx(parsedTracks),
                                    };
                                }
                            } catch (_) {}
                        }

                        const nktkParser = findNktkParser();
                        debugInfo.parserFound = !!nktkParser;
                        if (nktkParser && typeof nktkParser.parseNktkSequence === 'function') {
                            try {
                                const response = await fetch(`https://tracks.nakarte.me/track/${trackId}`, {
                                    credentials: 'include',
                                });
                                if (response.ok) {
                                    const binary = binaryStringFromArrayBuffer(await response.arrayBuffer());
                                    const parsedRaw = nktkParser.parseNktkSequence(binary);
                                    const parsedTracks = extractTracksFromGeoData(parsedRaw);
                                    if (parsedTracks.length) {
                                        return {
                                            source: 'nktk_direct_fetch',
                                            gpx: buildGpx(parsedTracks),
                                        };
                                    }
                                }
                            } catch (_) {}
                        }
                    }

                    let trackList = null;
                    let trackManager = null;
                    let fallbackTrack = null;
                    for (let i = 0; i < 120; i++) {
                        trackList = findTrackList();
                        trackManager = findTrackManager();
                        fallbackTrack = findTrackFallback();

                        if ((trackList && readTrackListTracks(trackList).length > 0) ||
                            (trackManager && Array.isArray(trackManager.tracks) && trackManager.tracks.length > 0) ||
                            !!fallbackTrack) {
                            break;
                        }
                        await sleep(250);
                    }

                    debugInfo.trackListFound = !!trackList;
                    debugInfo.trackManagerFound = !!trackManager;

                    if (trackList) {
                        const trackListTracks = readTrackListTracks(trackList);
                        if (trackListTracks.length > 0) {
                            const tracksData = [];
                            for (const tlTrack of trackListTracks) {
                                const exportResult = await trackList.exportTrackAsFile(
                                    tlTrack,
                                    (segments, name) => {
                                        const normalized = trackToSegmentsFromExport(segments);
                                        if (!normalized.length) {
                                            return '';
                                        }
                                        return JSON.stringify({
                                            name: name || 'Track',
                                            segments: normalized,
                                        });
                                    },
                                    '.gpx',
                                    false,
                                    true
                                );

                                if (exportResult && typeof exportResult.content === 'string' && exportResult.content) {
                                    try {
                                        const parsedTrack = JSON.parse(exportResult.content);
                                        if (parsedTrack?.segments?.length) {
                                            tracksData.push(parsedTrack);
                                        }
                                    } catch (_) {}
                                }
                            }

                            if (tracksData.length > 0) {
                                return {
                                    source: 'tracklist_export',
                                    gpx: buildGpx(tracksData),
                                };
                            }
                        }
                    }

                    const tracksForFallback = [];
                    if (trackManager && Array.isArray(trackManager.tracks) && trackManager.tracks.length > 0) {
                        tracksForFallback.push(...trackManager.tracks);
                    } else {
                        const singleFallbackTrack = fallbackTrack || findTrackFallback();
                        if (singleFallbackTrack) {
                            tracksForFallback.push(singleFallbackTrack);
                        }
                    }

                    if (!tracksForFallback.length) {
                        throw new Error(`Track not found in nakarte runtime: ${JSON.stringify(debugInfo)}`);
                    }

                    if (tracksForFallback.length === 1 && typeof window.saveGpx === 'function') {
                        try {
                            const exported = window.saveGpx(tracksForFallback[0]);
                            if (typeof exported === 'string' && exported.includes('<gpx')) {
                                return {
                                    source: 'window_saveGpx',
                                    gpx: exported,
                                };
                            }
                        } catch (_) {}
                    }

                    const fallbackTracksData = [];
                    for (const track of tracksForFallback) {
                        const segments = normalizeTrackSegments(track);
                        if (segments.length) {
                            fallbackTracksData.push({
                                name: track?.name || 'Track',
                                segments,
                            });
                        }
                    }

                    if (!fallbackTracksData.length) {
                        throw new Error('Track found but no coordinates extracted');
                    }

                    return {
                        source: 'fallback_track_object',
                        gpx: buildGpx(fallbackTracksData),
                    };
                }
                """,
                track_id,
            )

            gpx_source = None
            if isinstance(gpx_data, dict):
                gpx_source = gpx_data.get("source")
                gpx_data = gpx_data.get("gpx")

            if not gpx_data:
                raise RuntimeError("Failed to extract GPX data from page")

            gpx_bytes = (
                gpx_data.encode("utf-8")
                if isinstance(gpx_data, str)
                else gpx_data
            )
            gpx_bytes = self.ensure_friendly_track_name(gpx_bytes, track_id)

            self.logger.info("gpx_downloaded", track_id=track_id, size=len(gpx_bytes), source=gpx_source)
            return gpx_bytes

        except PlaywrightTimeoutError as e:
            self.logger.error("browser_timeout", url=url, error=str(e))
            raise RuntimeError(f"Timeout while loading page: {str(e)}")
        except Exception as e:
            self.logger.error("gpx_download_error", url=url, error=str(e))
            raise RuntimeError(f"Failed to download GPX: {str(e)}")
        finally:
            if page:
                await page.close()

    async def close(self) -> None:
        """Close browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        self.logger.info("browser_closed")
