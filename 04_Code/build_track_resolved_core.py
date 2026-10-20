#!/usr/bin/env python3
"""Reproducible polar-low data integration and quality-control pipeline.

No pandas/openpyxl are used. XLSX files are read from their OOXML content with
Python's standard library. Outputs: SQLite database, CSV tables, QA JSON, tests,
and publication-ready figures.
"""
from __future__ import annotations
import argparse, bisect, csv, hashlib, json, math, os, re, shutil, sqlite3, statistics, zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
import matplotlib.pyplot as plt

NS = {
    'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}
LIT_SOURCES = ['Golubkin', 'Noer', 'Rojo', 'Smirnova', 'Verezemskaya', 'Yanase']


def col_idx(ref: str) -> int:
    s = re.match(r'([A-Z]+)', ref).group(1)
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx_first_sheet(path: Path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('a:si', NS):
                shared.append(''.join((t.text or '') for t in si.iter('{%s}t' % NS['a'])))
        wbroot = ET.fromstring(z.read('xl/workbook.xml'))
        relroot = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rels = {r.get('Id'): r.get('Target') for r in relroot}
        sh = wbroot.find('a:sheets/a:sheet', NS)
        target = rels[sh.get('{%s}id' % NS['r'])].lstrip('/')
        if not target.startswith('xl/'):
            target = 'xl/' + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.findall('.//a:sheetData/a:row', NS):
            vals = {}
            for c in row.findall('a:c', NS):
                idx = col_idx(c.get('r'))
                typ = c.get('t')
                v = c.find('a:v', NS)
                if typ == 'inlineStr':
                    t = c.find('a:is/a:t', NS)
                    val = t.text if t is not None else ''
                elif v is None:
                    val = ''
                else:
                    raw = v.text
                    if typ == 's':
                        val = shared[int(raw)]
                    elif typ == 'b':
                        val = bool(int(raw))
                    else:
                        try:
                            num = float(raw)
                            val = int(num) if num.is_integer() else num
                        except Exception:
                            val = raw
                vals[idx] = val
            if vals:
                mx = max(vals)
                rows.append([vals.get(i, '') for i in range(mx + 1)])
        maxc = max(map(len, rows))
        return [r + [''] * (maxc - len(r)) for r in rows]


def parse_dt(s):
    if s is None or s == '':
        return None
    if isinstance(s, (int, float)):
        return datetime(1899, 12, 30) + timedelta(days=float(s))
    st = str(s).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(st, fmt)
        except ValueError:
            pass
    return None


def fnum(x):
    if x is None or x == '' or str(x).lower() in ('nan', 'none', 'na'):
        return None
    try:
        return float(x)
    except Exception:
        return None


def inum(x):
    if x is None or x == '':
        return None
    try:
        return int(float(x))
    except Exception:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def vals_clean(vals):
    return [v for v in vals if v is not None and math.isfinite(v)]


def safe_mean(vals):
    v = vals_clean(vals)
    return float(np.mean(v)) if v else None


def safe_min(vals):
    v = vals_clean(vals)
    return float(min(v)) if v else None


def safe_max(vals):
    v = vals_clean(vals)
    return float(max(v)) if v else None


def quantile(vals, q):
    v = vals_clean(vals)
    return float(np.quantile(v, q)) if v else None


def iso(v):
    return v.isoformat(sep=' ') if isinstance(v, datetime) else v


def json_safe(obj):
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat(sep=' ')
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def write_csv(path: Path, rows: list[dict], fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            w.writerow({k: iso(row.get(k)) for k in fieldnames})


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def bh_adjust(pvals):
    n = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(n)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        val = min(prev, pvals[i] * n / rank)
        adj[i], prev = val, val
    return adj.tolist()


def cliffs_delta(x, y):
    u = stats.mannwhitneyu(x, y, alternative='two-sided').statistic
    return float(2 * u / (len(x) * len(y)) - 1)


def welch_d(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return float((x.mean() - y.mean()) / math.sqrt((x.var(ddof=1) + y.var(ddof=1)) / 2))


def load_all(inp: Path):
    required = {
        'cyclone_infos': inp / 'cyclone_infos.xlsx',
        'era5_tracks': inp / 'ERA5_tracks.xlsx',
        'monthly': inp / 'Final_Monthly_total(1).xlsx',
        'Rojo_raw': inp / 'Rojo-etal_2019.tab',
    }
    for s in LIT_SOURCES:
        required[s] = inp / f'{s}.csv'
    missing = [str(p) for p in required.values() if not p.exists()]
    if missing:
        raise FileNotFoundError('Missing input files: ' + ', '.join(missing))

    eraw, craw, mraw = (read_xlsx_first_sheet(required[k]) for k in ('era5_tracks', 'cyclone_infos', 'monthly'))
    eh, ch, mh = eraw[0], craw[0], mraw[0]
    era = []
    for r in eraw[1:]:
        d = dict(zip(eh, r))
        era.append({'track_id': str(inum(d['ID'])), 'time': parse_dt(d['time']), 'lon': fnum(d['lon']),
                    'lat': fnum(d['lat']), 'vort850_1e5_s1': fnum(d['ζ_smth850']),
                    'vortex_diameter_km': fnum(d['r']), 'slp_lon': fnum(d['slp_lon']),
                    'slp_lat': fnum(d['slp_lat']), 'slp_hpa': fnum(d['slp'])})
    cloud = []
    for r in craw[1:]:
        d = dict(zip(ch, r))
        cloud.append({'track_id': str(inum(d['ID'])), 'step': inum(d['step']),
                      'morphology': str(d['class']) if d['class'] != '' else None,
                      'lon': fnum(d['lon']), 'lat': fnum(d['lat']), 'time': parse_dt(d['time']),
                      'width_km': fnum(d['width']), 'length_km': fnum(d['length']),
                      'satellite': str(d['AVHRR_satellite']) if d['AVHRR_satellite'] != '' else None,
                      'wind_time': parse_dt(d['wind_time']), 'max_wind_ms': fnum(d['max_wind']),
                      'valid_fraction': fnum(d['valid_fraction'])})
    monthly = []
    for r in mraw[1:]:
        d = dict(zip(mh, r))
        if inum(d['Year']) is not None:
            monthly.append({'year': inum(d['Year']), 'month': inum(d['Month']),
                            'X2': fnum(d['X2']), 'X1': fnum(d['X1']), 'Y': fnum(d['Y'])})
    lit = []
    for src in LIT_SOURCES:
        with required[src].open(encoding='utf-8-sig', newline='') as f:
            for d in csv.DictReader(f):
                lit.append({'source': src, 'original_id': str(d['ID']).strip(), 'step': inum(d['step']),
                    'lon': fnum(d['lon']), 'lat': fnum(d['lat']), 'time': parse_dt(d['time']),
                    'pl_track': inum(d['PL_track']), 'pl_time_step': fnum(d['PL_time_step']),
                    'ref_id_1': str(d['PLlist_match']).strip() if d['PLlist_match'] != '' else None,
                    'ref_id_2': str(d['PLlist_match_2']).strip() if d['PLlist_match_2'] != '' else None,
                    'ref_id_3': str(d['PLlist_match_3']).strip() if d['PLlist_match_3'] != '' else None,
                    'vort850_1e5_s1': fnum(d['rel_vort_850_smth']),
                    'vortex_diameter_km': fnum(d['vortex_diameter']),
                    'theta_trop_k': fnum(d['theta_trop_mean250']),
                    'theta500_minus_theta_sst_k': fnum(d['theta_diff_500-sst_mean250']),
                    'slp_hpa': fnum(d['slp']), 'sst_minus_t500_k': fnum(d['SST-T_500_mean250']),
                    'u_surface_max_ms': fnum(d['U_surface_max250']),
                    'u_trop_poleward_ms': fnum(d['U_trop_polew']),
                    'land_distance_km': fnum(d['land_dist']),
                    'theta500_minus_theta925_k': fnum(d['theta_diff_500-925_mean250'])})
    lines = required['Rojo_raw'].read_text(encoding='utf-8-sig').splitlines()
    hi = next(i for i, line in enumerate(lines) if line.startswith('ID (PolarLowID)'))
    hdr = lines[hi].split('\t')
    obs = []
    for line in lines[hi + 1:]:
        if not line.strip():
            continue
        v = line.split('\t') + [''] * len(hdr)
        d = dict(zip(hdr, v))
        obs.append({'raw_pl_id': d[hdr[0]].strip(), 'time': parse_dt(d['Date/Time']),
                    'season': d['Season'] or None, 'observation_no': inum(d['Obs']),
                    'lat': fnum(d['Latitude']), 'lon': fnum(d['Longitude']),
                    'diameter1_km': fnum(d[hdr[6]]), 'diameter2_km': fnum(d[hdr[7]]),
                    'morphology': d[hdr[8]] or None, 'stage': d[hdr[9]] or None,
                    'comment1': d[hdr[10]] or None, 'comment2': d[hdr[11]] or None,
                    'comment3': d[hdr[12]] or None, 'min_slp_hpa': fnum(d[hdr[13]]),
                    'wind10min_raw': d[hdr[14]] or None, 'gust3s_raw': d[hdr[15]] or None})
    return required, era, cloud, monthly, lit, obs


def canonicalize(lit):
    grp = defaultdict(list)
    for r in lit:
        grp[(r['original_id'], r['time'])].append(r)
    numeric = ['lon', 'lat', 'vort850_1e5_s1', 'vortex_diameter_km', 'theta_trop_k',
               'theta500_minus_theta_sst_k', 'slp_hpa', 'sst_minus_t500_k',
               'u_surface_max_ms', 'u_trop_poleward_ms', 'land_distance_km',
               'theta500_minus_theta925_k']
    canonical, conflicts = [], []
    for (oid, t), rows in sorted(grp.items(), key=lambda x: (x[0][0], x[0][1])):
        latvals = [x['lat'] for x in rows if x['lat'] is not None]
        out = {'canonical_track_id': 'LIT_' + oid, 'original_id': oid, 'time': t,
               'hemisphere': 'SH' if statistics.median(latvals) < 0 else 'NH',
               'sources': '|'.join(sorted(set(x['source'] for x in rows))),
               'pl_track_any': max(x['pl_track'] or 0 for x in rows),
               'pl_time_step_any': max(x['pl_time_step'] or 0 for x in rows),
               'ref_ids': '|'.join(sorted(set(z for x in rows for z in
                                           [x['ref_id_1'], x['ref_id_2'], x['ref_id_3']] if z)))}
        for fld in numeric:
            vals = [x[fld] for x in rows if x[fld] is not None]
            out[fld] = statistics.mean(vals) if vals else None
            tol = 0.05 if fld in ('lon', 'lat') else 1e-6
            if vals and max(vals) - min(vals) > tol:
                conflicts.append({'original_id': oid, 'time': t, 'field': fld,
                                  'minimum': min(vals), 'maximum': max(vals), 'sources': out['sources']})
        canonical.append(out)
    return canonical, conflicts


def track_summaries(canonical, lit):
    members, labels, pts_by = defaultdict(set), defaultdict(list), defaultdict(list)
    for r in lit:
        cid = 'LIT_' + r['original_id']
        members[cid].add(r['source']); labels[cid].append(r['pl_track'] or 0)
    for r in canonical:
        pts_by[r['canonical_track_id']].append(r)
    out = []
    for cid, pts in pts_by.items():
        pts.sort(key=lambda x: x['time'])
        times = [p['time'] for p in pts]
        speeds, gaps = [], []
        for a, b in zip(pts[:-1], pts[1:]):
            dh = (b['time'] - a['time']).total_seconds() / 3600
            if dh > 0:
                gaps.append(dh)
                d = haversine_km(a['lat'], a['lon'], b['lat'], b['lon'])
                if d is not None:
                    speeds.append(d / dh)
        vmax = safe_max([p['vort850_1e5_s1'] for p in pts])
        tmi = next((p for p in pts if p['vort850_1e5_s1'] == vmax), pts[0])
        mt = safe_mean([p['theta_trop_k'] for p in pts])
        ms = safe_min([p['theta500_minus_theta_sst_k'] for p in pts])
        md = safe_max([p['vortex_diameter_km'] for p in pts])
        c1, c2, c3, c4 = mt is not None and mt < 300.8, ms is not None and ms < 11.0, vmax is not None and vmax > 20.0, md is not None and md < 430.0
        out.append({'canonical_track_id': cid, 'original_id': pts[0]['original_id'],
            'hemisphere': pts[0]['hemisphere'], 'sources': '|'.join(sorted(members[cid])),
            'source_count': len(members[cid]), 'pl_track_any': max(labels[cid]),
            'start_time': times[0], 'end_time': times[-1], 'n_points': len(pts),
            'duration_h': (times[-1] - times[0]).total_seconds() / 3600 if len(times) > 1 else 0,
            'median_step_h': float(np.median(gaps)) if gaps else None, 'max_gap_h': safe_max(gaps),
            'median_speed_kmh': float(np.median(speeds)) if speeds else None,
            'p95_speed_kmh': quantile(speeds, .95), 'max_speed_kmh': safe_max(speeds),
            'mean_lat': safe_mean([p['lat'] for p in pts]), 'mean_lon': safe_mean([p['lon'] for p in pts]),
            'mean_theta_trop_k': mt, 'min_theta500_minus_theta_sst_k': ms,
            'max_vort850_1e5_s1': vmax, 'max_vortex_diameter_km': md,
            'min_slp_hpa': safe_min([p['slp_hpa'] for p in pts]),
            'max_sst_minus_t500_k': safe_max([p['sst_minus_t500_k'] for p in pts]),
            'max_surface_wind_ms': safe_max([p['u_surface_max_ms'] for p in pts]),
            'tmi_time': tmi['time'], 'tmi_lat': tmi['lat'], 'tmi_lon': tmi['lon'],
            'tmi_diameter_km': tmi['vortex_diameter_km'], 'tmi_slp_hpa': tmi['slp_hpa'],
            'tmi_sst_minus_t500_k': tmi['sst_minus_t500_k'], 'tmi_theta_trop_k': tmi['theta_trop_k'],
            'tmi_land_distance_km': tmi['land_distance_km'],
            'criterion_polar_front': int(c1), 'criterion_static_stability': int(c2),
            'criterion_intensity': int(c3), 'criterion_mesoscale': int(c4),
            'passes_all_stoll_criteria': int(c1 and c2 and c3 and c4)})
    return out


def source_criteria(lit):
    out = []
    for src in LIT_SOURCES:
        by = defaultdict(list)
        for r in lit:
            if r['source'] == src:
                by[r['original_id']].append(r)
        ss = []
        for oid, pts in by.items():
            mt = safe_mean([p['theta_trop_k'] for p in pts]); ms = safe_min([p['theta500_minus_theta_sst_k'] for p in pts])
            vv = safe_max([p['vort850_1e5_s1'] for p in pts]); dd = safe_max([p['vortex_diameter_km'] for p in pts])
            c1, c2, c3, c4 = (mt is not None and mt < 300.8), (ms is not None and ms < 11), (vv is not None and vv > 20), (dd is not None and dd < 430)
            ss.append({'pl_track_any': max(p['pl_track'] or 0 for p in pts), 'c1': c1, 'c2': c2, 'c3': c3, 'c4': c4,
                       'all': c1 and c2 and c3 and c4, 'hemisphere': 'SH' if safe_mean([p['lat'] for p in pts]) < 0 else 'NH'})
        for subset, sub in [('all_candidates', ss), ('PL_track_positive', [r for r in ss if r['pl_track_any'] == 1])]:
            out.append({'source': src, 'hemisphere': ss[0]['hemisphere'], 'subset': subset, 'n_tracks': len(sub),
                        'polar_front_pass_pct': 100 * np.mean([r['c1'] for r in sub]),
                        'static_stability_pass_pct': 100 * np.mean([r['c2'] for r in sub]),
                        'intensity_pass_pct': 100 * np.mean([r['c3'] for r in sub]),
                        'mesoscale_pass_pct': 100 * np.mean([r['c4'] for r in sub]),
                        'all_criteria_pass_pct': 100 * np.mean([r['all'] for r in sub])})
    return out


def match_clouds(era, cloud):
    by = defaultdict(list)
    for r in era: by[r['track_id']].append(r)
    for arr in by.values(): arr.sort(key=lambda x: x['time'])
    matches, speed_rows, summaries = [], [], []
    for c in cloud:
        arr = by.get(c['track_id'], [])
        times = [x['time'] for x in arr]
        pos = bisect.bisect_left(times, c['time'])
        cand = [arr[j] for j in (pos - 1, pos) if 0 <= j < len(arr)]
        e = min(cand, key=lambda x: abs((x['time'] - c['time']).total_seconds())) if cand else None
        matches.append({'track_id': c['track_id'], 'cloud_step': c['step'], 'cloud_time': c['time'],
                        'cloud_lon': c['lon'], 'cloud_lat': c['lat'], 'morphology': c['morphology'],
                        'width_km': c['width_km'], 'length_km': c['length_km'], 'satellite': c['satellite'],
                        'wind_time': c['wind_time'], 'max_wind_ms': c['max_wind_ms'], 'valid_fraction': c['valid_fraction'],
                        'era_time': e['time'] if e else None, 'era_lon': e['lon'] if e else None, 'era_lat': e['lat'] if e else None,
                        'time_diff_min': abs((e['time'] - c['time']).total_seconds()) / 60 if e else None,
                        'distance_km': haversine_km(c['lat'], c['lon'], e['lat'], e['lon']) if e else None,
                        'era_vort850_1e5_s1': e['vort850_1e5_s1'] if e else None,
                        'era_diameter_km': e['vortex_diameter_km'] if e else None, 'era_slp_hpa': e['slp_hpa'] if e else None})
    for tid, pts in by.items():
        pts.sort(key=lambda x: x['time']); gaps, speeds = [], []
        for a, b in zip(pts[:-1], pts[1:]):
            dh = (b['time'] - a['time']).total_seconds() / 3600
            d = haversine_km(a['lat'], a['lon'], b['lat'], b['lon'])
            sp = d / dh if dh > 0 else None
            gaps.append(dh)
            if sp is not None: speeds.append(sp)
            speed_rows.append({'track_id': tid, 'time1': a['time'], 'time2': b['time'], 'gap_h': dh,
                               'distance_km': d, 'speed_kmh': sp, 'flag_gt100': int(sp is not None and sp > 100),
                               'flag_gt200': int(sp is not None and sp > 200)})
        summaries.append({'track_id': tid, 'start_time': pts[0]['time'], 'end_time': pts[-1]['time'],
            'n_points': len(pts), 'duration_h': (pts[-1]['time'] - pts[0]['time']).total_seconds() / 3600,
            'median_step_h': float(np.median(gaps)) if gaps else None, 'max_gap_h': safe_max(gaps),
            'max_vort850_1e5_s1': safe_max([p['vort850_1e5_s1'] for p in pts]),
            'min_slp_hpa': safe_min([p['slp_hpa'] for p in pts]),
            'median_speed_kmh': float(np.median(speeds)) if speeds else None, 'p95_speed_kmh': quantile(speeds, .95),
            'max_speed_kmh': safe_max(speeds), 'speed_gt100_count': sum(s > 100 for s in speeds),
            'speed_gt200_count': sum(s > 200 for s in speeds)})
    valid = [r for r in matches if r['distance_km'] is not None]
    stats_out = {'n_cloud_features': len(matches), 'n_tracks': len(set(r['track_id'] for r in matches)),
        'median_time_diff_min': float(np.median([r['time_diff_min'] for r in valid])),
        'p95_time_diff_min': quantile([r['time_diff_min'] for r in valid], .95),
        'median_distance_km': float(np.median([r['distance_km'] for r in valid])),
        'p95_distance_km': quantile([r['distance_km'] for r in valid], .95),
        'pct_within_60min_120km': 100 * np.mean([r['time_diff_min'] <= 60 and r['distance_km'] <= 120 for r in valid]),
        'pct_within_180min_250km': 100 * np.mean([r['time_diff_min'] <= 180 and r['distance_km'] <= 250 for r in valid]),
        'n_wind_records': sum(r['max_wind_ms'] is not None for r in matches),
        'n_tracks_wind_gt15': len(set(r['track_id'] for r in matches if r['max_wind_ms'] is not None and r['max_wind_ms'] > 15))}
    return matches, summaries, speed_rows, stats_out


def match_rojo(obs, lit):
    rows = [r for r in lit if r['source'] == 'Rojo']
    idx = defaultdict(list)
    for r in rows:
        for ref in (r['ref_id_1'], r['ref_id_2'], r['ref_id_3']):
            if ref:
                try:
                    z = float(ref); ref = str(int(z)) if z.is_integer() else ref
                except Exception:
                    pass
                idx[ref].append(r)
    for arr in idx.values(): arr.sort(key=lambda x: x['time'])
    matches = []
    for o in obs:
        arr = idx.get(o['raw_pl_id'], []); times = [x['time'] for x in arr]
        pos = bisect.bisect_left(times, o['time'])
        cand = [arr[j] for j in (pos - 1, pos) if 0 <= j < len(arr)]
        e = min(cand, key=lambda x: abs((x['time'] - o['time']).total_seconds())) if cand else None
        td = abs((e['time'] - o['time']).total_seconds()) / 60 if e else None
        dist = haversine_km(o['lat'], o['lon'], e['lat'], e['lon']) if e else None
        matches.append({**o, 'matched': int(e is not None), 'era_track_id': e['original_id'] if e else None,
                        'era_time': e['time'] if e else None, 'era_lat': e['lat'] if e else None,
                        'era_lon': e['lon'] if e else None, 'time_diff_min': td, 'distance_km': dist,
                        'within_60min_120km': int(e is not None and td <= 60 and dist <= 120)})
    cand = [r for r in matches if r['matched']]
    by = defaultdict(list)
    for r in matches: by[r['raw_pl_id']].append(r)
    return matches, {'n_raw_observations': len(obs), 'n_raw_tracks': len(by),
        'n_observations_with_reference_candidate': len(cand),
        'pct_observations_with_reference_candidate': 100 * len(cand) / len(obs),
        'pct_candidate_obs_within_60min_120km': 100 * np.mean([r['within_60min_120km'] for r in cand]),
        'median_candidate_distance_km': float(np.median([r['distance_km'] for r in cand])),
        'median_candidate_time_diff_min': float(np.median([r['time_diff_min'] for r in cand])),
        'n_raw_tracks_with_candidate': len(set(r['raw_pl_id'] for r in cand)),
        'n_raw_tracks_majority_matched': sum(np.mean([x['within_60min_120km'] for x in rr]) > .5 for rr in by.values())}


def hemisphere_tests(tracks):
    variables = [('duration_h', 'Track duration (h)'), ('mean_theta_trop_k', 'Lifetime-mean tropopause potential temperature (K)'),
        ('min_theta500_minus_theta_sst_k', 'Lifetime-min potential static stability (K)'),
        ('max_vort850_1e5_s1', 'Lifetime-max 850-hPa vorticity (1e-5 s-1)'),
        ('max_vortex_diameter_km', 'Lifetime-max vortex diameter (km)'), ('min_slp_hpa', 'Lifetime-min sea-level pressure (hPa)'),
        ('max_sst_minus_t500_k', 'Lifetime-max SST-T500 (K)'), ('max_surface_wind_ms', 'Lifetime-max surface wind (m s-1)'),
        ('tmi_diameter_km', 'Vortex diameter at maximum intensity (km)'), ('tmi_slp_hpa', 'SLP at maximum intensity (hPa)'),
        ('tmi_sst_minus_t500_k', 'SST-T500 at maximum intensity (K)'), ('tmi_theta_trop_k', 'Tropopause potential temperature at TMI (K)'),
        ('tmi_land_distance_km', 'Distance to land at maximum intensity (km)')]
    out = []
    subsets = [('all_unique_candidates', tracks), ('standardized_PL_criteria', [r for r in tracks if r['passes_all_stoll_criteria']]),
               ('catalog_PL_track_positive', [r for r in tracks if r['pl_track_any']])]
    for subset, rows in subsets:
        block = []
        for var, label in variables:
            x = [r[var] for r in rows if r['hemisphere'] == 'NH' and r[var] is not None]
            y = [r[var] for r in rows if r['hemisphere'] == 'SH' and r[var] is not None]
            if len(x) < 5 or len(y) < 5: continue
            mw, ks, wt = stats.mannwhitneyu(x, y, alternative='two-sided'), stats.ks_2samp(x, y), stats.ttest_ind(x, y, equal_var=False)
            block.append({'subset': subset, 'variable': var, 'label': label, 'n_NH': len(x), 'n_SH': len(y),
                'NH_mean': np.mean(x), 'SH_mean': np.mean(y), 'NH_median': np.median(x), 'SH_median': np.median(y),
                'median_difference_NH_minus_SH': np.median(x) - np.median(y), 'mann_whitney_U': mw.statistic,
                'mann_whitney_p': mw.pvalue, 'cliffs_delta_NH_vs_SH': cliffs_delta(x, y), 'ks_D': ks.statistic,
                'ks_p': ks.pvalue, 'welch_t': wt.statistic, 'welch_p': wt.pvalue, 'welch_d_NH_minus_SH': welch_d(x, y)})
        for r, q in zip(block, bh_adjust([r['mann_whitney_p'] for r in block])): r['mann_whitney_p_BH'] = q
        out.extend(block)
    return out


def rf_model(rows):
    feats = ['duration_h', 'mean_theta_trop_k', 'min_theta500_minus_theta_sst_k', 'max_vort850_1e5_s1',
             'max_vortex_diameter_km', 'min_slp_hpa', 'max_sst_minus_t500_k', 'max_surface_wind_ms']
    X = np.array([[r[f] if r[f] is not None else np.nan for f in feats] for r in rows], dtype=float)
    y = np.array([1 if r['hemisphere'] == 'SH' else 0 for r in rows])
    meds = np.nanmedian(X, axis=0); ii = np.where(np.isnan(X)); X[ii] = np.take(meds, ii[1])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model = RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight='balanced', random_state=42, n_jobs=1)
    prob = cross_val_predict(model, X, y, cv=cv, method='predict_proba', n_jobs=1)[:, 1]
    pred = (prob >= .5).astype(int); model.fit(X, y)
    perm = permutation_importance(model, X, y, n_repeats=10, random_state=42, n_jobs=1, scoring='roc_auc')
    imp = sorted([{'feature': f, 'mean': m, 'sd': s} for f, m, s in zip(feats, perm.importances_mean, perm.importances_std)], key=lambda z: -z['mean'])
    return {'n': len(y), 'n_NH': int(sum(y == 0)), 'n_SH': int(sum(y == 1)), 'roc_auc': roc_auc_score(y, prob),
            'accuracy': accuracy_score(y, pred), 'balanced_accuracy': balanced_accuracy_score(y, pred),
            'confusion_matrix': confusion_matrix(y, pred).tolist(), 'permutation_importance': imp,
            'warning': 'Hemisphere is confounded with source catalogue (all SH candidates originate from Verezemskaya); interpret as exploratory.'}


def monthly_qa(monthly):
    ordered = sorted(monthly, key=lambda x: (x['year'], x['month']))
    duplicates = len(ordered) - len(set((r['year'], r['month']) for r in ordered))
    missing_months = []
    if ordered:
        cur = datetime(ordered[0]['year'], ordered[0]['month'], 1); end = datetime(ordered[-1]['year'], ordered[-1]['month'], 1)
        have = {(r['year'], r['month']) for r in ordered}
        while cur <= end:
            if (cur.year, cur.month) not in have: missing_months.append(cur.strftime('%Y-%m'))
            cur = datetime(cur.year + (cur.month == 12), 1 if cur.month == 12 else cur.month + 1, 1)
    return {'n_rows': len(ordered), 'start': f"{ordered[0]['year']}-{ordered[0]['month']:02d}",
            'end': f"{ordered[-1]['year']}-{ordered[-1]['month']:02d}", 'duplicate_months': duplicates,
            'missing_months': missing_months, 'missing_X1': sum(r['X1'] is None for r in ordered),
            'missing_X2': sum(r['X2'] is None for r in ordered), 'missing_Y': sum(r['Y'] is None for r in ordered),
            'interpretation_status': 'Variable definitions/units not supplied; retained as an auxiliary monthly table and not joined to storm-level records.'}


def make_db(path, tables):
    if path.exists(): path.unlink()
    con = sqlite3.connect(path)
    for name, rows in tables.items():
        if not rows: continue
        fields = list(rows[0].keys())
        def sql_type(field):
            vals = [r.get(field) for r in rows if r.get(field) is not None]
            if not vals: return 'TEXT'
            sample = vals[0]
            if isinstance(sample, bool) or isinstance(sample, int) or isinstance(sample, np.integer): return 'INTEGER'
            if isinstance(sample, float) or isinstance(sample, np.floating): return 'REAL'
            return 'TEXT'
        cols = ','.join('"%s" %s' % (f, sql_type(f)) for f in fields)
        con.execute(f'CREATE TABLE "{name}" ({cols})')
        q = ','.join('?' for _ in fields)
        payload=[]
        for r in rows:
            row=[]
            for f in fields:
                v=r.get(f)
                if isinstance(v, datetime): v=v.isoformat(sep=' ')
                elif isinstance(v, (np.integer,)): v=int(v)
                elif isinstance(v, (np.floating,)): v=float(v)
                row.append(v)
            payload.append(row)
        con.executemany(f'INSERT INTO "{name}" VALUES ({q})', payload)
    con.execute('CREATE INDEX idx_canonical_track_time ON canonical_track_points(canonical_track_id,time)')
    con.execute('CREATE INDEX idx_impmct_track_time ON impmct_era5_track_points(track_id,time)')
    con.execute('CREATE INDEX idx_track_summary_hemi ON literature_track_summary(hemisphere)')
    con.execute('CREATE INDEX idx_catalogue_membership ON catalogue_membership(canonical_track_id,source)')
    con.execute('CREATE VIEW standardized_polar_lows AS SELECT * FROM literature_track_summary WHERE passes_all_stoll_criteria=1')
    con.execute('CREATE VIEW standardized_polar_low_points AS SELECT p.* FROM canonical_track_points p JOIN standardized_polar_lows s USING(canonical_track_id)')
    con.execute('CREATE VIEW qa_warnings AS SELECT * FROM qa_results WHERE status IN (\'WARN\',\'FAIL\')')
    con.commit(); con.close()


def make_figures(figdir, criteria, tracks, cloud_matches, era_summ):
    figdir.mkdir(parents=True, exist_ok=True)
    # 1 source counts
    counts = Counter(s for r in tracks for s in r['sources'].split('|'))
    plt.figure(figsize=(8, 4.5)); plt.bar(list(counts.keys()), list(counts.values())); plt.ylabel('Tracks'); plt.title('Track membership by source catalogue'); plt.xticks(rotation=30, ha='right'); plt.tight_layout(); plt.savefig(figdir/'01_source_track_counts.png', dpi=220); plt.close()
    # 2 criteria pass
    rows = [r for r in criteria if r['subset'] == 'all_candidates']
    plt.figure(figsize=(8, 4.5)); plt.bar([r['source'] for r in rows], [r['all_criteria_pass_pct'] for r in rows]); plt.ylabel('Tracks satisfying all four criteria (%)'); plt.title('Reproduction of standardized polar-low criteria'); plt.xticks(rotation=30, ha='right'); plt.ylim(0, 100); plt.tight_layout(); plt.savefig(figdir/'02_stoll_criteria_retention.png', dpi=220); plt.close()
    # 3 NH/SH distributions for standardized PLs
    pl = [r for r in tracks if r['passes_all_stoll_criteria']]
    nh = [r['max_vort850_1e5_s1'] for r in pl if r['hemisphere']=='NH']; sh = [r['max_vort850_1e5_s1'] for r in pl if r['hemisphere']=='SH']
    plt.figure(figsize=(6, 4.5)); plt.boxplot([nh, sh], tick_labels=['NH','SH'], showfliers=False); plt.ylabel('Lifetime maximum vorticity (1e-5 s-1)'); plt.title('Standardized polar-low subset'); plt.tight_layout(); plt.savefig(figdir/'03_hemisphere_vorticity_boxplot.png', dpi=220); plt.close()
    # 4 cloud matching distance
    d=[r['distance_km'] for r in cloud_matches if r['distance_km'] is not None]
    plt.figure(figsize=(7,4.5)); plt.hist(d, bins=50); plt.axvline(120, linestyle='--'); plt.xlabel('Cloud-to-nearest ERA5 vortex distance (km)'); plt.ylabel('Cloud features'); plt.title('IMPMCT spatial matching quality'); plt.tight_layout(); plt.savefig(figdir/'04_cloud_era5_matching_distance.png', dpi=220); plt.close()
    # 5 speed flags
    med=[r['median_speed_kmh'] for r in era_summ if r['median_speed_kmh'] is not None]
    plt.figure(figsize=(7,4.5)); plt.hist(med, bins=45); plt.xlabel('Track median translation speed (km h-1)'); plt.ylabel('Tracks'); plt.title('ERA5 track-motion quality control'); plt.tight_layout(); plt.savefig(figdir/'05_track_speed_qc.png', dpi=220); plt.close()
    # 6 monthly occurrence by hemisphere, candidate points unique tracks by TMI month
    months=np.arange(1,13); nhc=Counter(r['tmi_time'].month for r in tracks if r['hemisphere']=='NH'); shc=Counter(r['tmi_time'].month for r in tracks if r['hemisphere']=='SH')
    w=.38; plt.figure(figsize=(8,4.5)); plt.bar(months-w/2,[nhc[m] for m in months],width=w,label='NH'); plt.bar(months+w/2,[shc[m] for m in months],width=w,label='SH'); plt.xticks(months); plt.xlabel('Month of maximum intensity'); plt.ylabel('Unique candidate tracks'); plt.title('Seasonal sampling by hemisphere (catalogue-dependent)'); plt.legend(); plt.tight_layout(); plt.savefig(figdir/'06_seasonal_sampling.png', dpi=220); plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', default='/mnt/data')
    ap.add_argument('--output-dir', default='/mnt/data/polar_low_integrated_package')
    args = ap.parse_args(); inp, out = Path(args.input_dir), Path(args.output_dir)
    for d in (out/'exports', out/'figures', out/'reports'): d.mkdir(parents=True, exist_ok=True)
    files, era, cloud, monthly, lit, obs = load_all(inp)
    canonical, conflicts = canonicalize(lit)
    tracks = track_summaries(canonical, lit)
    criteria = source_criteria(lit)
    cloud_matches, era_summ, era_speeds, cloud_stats = match_clouds(era, cloud)
    rojo_matches, rojo_stats = match_rojo(obs, lit)
    htests = hemisphere_tests(tracks)
    rf_all = rf_model(tracks)
    rf_pl = rf_model([r for r in tracks if r['passes_all_stoll_criteria']])
    monthly_stats = monthly_qa(monthly)

    membership=[]
    for r in lit:
        membership.append({'canonical_track_id':'LIT_'+r['original_id'],'source':r['source'],'original_id':r['original_id'],
                           'ref_id_1':r['ref_id_1'],'ref_id_2':r['ref_id_2'],'ref_id_3':r['ref_id_3']})
    # unique membership rows
    membership=[dict(t) for t in sorted(set(tuple(sorted(x.items())) for x in membership))]

    source_files=[{'logical_name':k,'filename':p.name,'sha256':sha256(p),'size_bytes':p.stat().st_size} for k,p in files.items()]
    qa_rows=[]
    def qa(area,metric,value,status='INFO',note=''):
        qa_rows.append({'area':area,'metric':metric,'value':value,'status':status,'note':note})
    qa('IMPMCT','ERA5 track points',len(era)); qa('IMPMCT','ERA5 tracks',len(set(r['track_id'] for r in era)))
    qa('IMPMCT','cloud features',len(cloud)); qa('IMPMCT','wind records',cloud_stats['n_wind_records'])
    qa('IMPMCT','cloud match within 60 min and 120 km (%)',cloud_stats['pct_within_60min_120km'],'PASS' if cloud_stats['pct_within_60min_120km']>=90 else 'WARN')
    qa('IMPMCT','track intervals >100 km/h',sum(r['flag_gt100'] for r in era_speeds),'WARN','Retained and flagged; likely jumps/split-merge artifacts, not automatically deleted.')
    qa('IMPMCT','track intervals >200 km/h',sum(r['flag_gt200'] for r in era_speeds),'WARN')
    qa('Literature integration','raw source rows',len(lit)); qa('Literature integration','canonical unique points',len(canonical)); qa('Literature integration','canonical unique tracks',len(tracks))
    qa('Literature integration','exact duplicate source rows removed',len(lit)-len(canonical),'PASS')
    qa('Literature integration','numeric conflicts across exact duplicate points',len(conflicts),'PASS' if not conflicts else 'WARN')
    qa('Rojo validation','raw observation points',len(obs)); qa('Rojo validation','candidate observations within 60 min and 120 km (%)',rojo_stats['pct_candidate_obs_within_60min_120km'],'INFO')
    qa('Monthly auxiliary','rows',len(monthly)); qa('Monthly auxiliary','missing months',len(monthly_stats['missing_months']),'PASS' if not monthly_stats['missing_months'] else 'WARN')
    qa('Monthly auxiliary','missing X1',monthly_stats['missing_X1'],'WARN','Variable definitions and units are unknown; no scientific interpretation performed.')

    tables={'source_files':source_files,'impmct_era5_track_points':era,'impmct_cloud_features':cloud,
            'impmct_cloud_era5_matches':cloud_matches,'impmct_track_summary':era_summ,'impmct_motion_intervals':era_speeds,
            'literature_source_points':lit,'canonical_track_points':canonical,'literature_track_summary':tracks,
            'catalogue_membership':membership,'criteria_summary':criteria,'rojo_raw_observations':obs,
            'rojo_observation_matches':rojo_matches,'monthly_auxiliary':monthly,'hemisphere_tests':htests,'qa_results':qa_rows}
    make_db(out/'integrated_polar_low_database.sqlite', tables)
    for name, rows in tables.items(): write_csv(out/'exports'/f'{name}.csv', rows)
    if conflicts: write_csv(out/'exports'/'deduplication_conflicts.csv', conflicts)
    make_figures(out/'figures', criteria, tracks, cloud_matches, era_summ)

    summary={'generated_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'source_files':source_files,
        'counts':{'impmct_era5_points':len(era),'impmct_tracks':len(set(r['track_id'] for r in era)),
                  'impmct_cloud_features':len(cloud),'literature_source_rows':len(lit),
                  'canonical_literature_points':len(canonical),'canonical_literature_tracks':len(tracks),
                  'NH_tracks':sum(r['hemisphere']=='NH' for r in tracks),'SH_tracks':sum(r['hemisphere']=='SH' for r in tracks),
                  'standardized_PL_tracks':sum(r['passes_all_stoll_criteria'] for r in tracks)},
        'cloud_era5_validation':cloud_stats,'rojo_validation':rojo_stats,'monthly_qa':monthly_stats,
        'criteria_summary':criteria,'exploratory_hemisphere_RF_all_candidates':rf_all,
        'exploratory_hemisphere_RF_standardized_PL':rf_pl,
        'warnings':['The Verezemskaya file is a Southern Ocean mesocyclone candidate list, not an all-positive polar-low catalogue.',
                    'Hemisphere comparisons are source-confounded because all SH candidates derive from one catalogue.',
                    'Fast translation intervals were flagged but not automatically removed.',
                    'The monthly X1/X2/Y table was not joined to storm records because variable definitions and units were not supplied.']}
    (out/'analysis_summary.json').write_text(json.dumps(json_safe(summary),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(json_safe(summary['counts']), indent=2))
    print(json.dumps(json_safe(cloud_stats), indent=2))
    print(json.dumps(json_safe(rojo_stats), indent=2))
    print('Database:', out/'integrated_polar_low_database.sqlite')

if __name__=='__main__':
    main()
