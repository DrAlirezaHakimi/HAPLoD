#!/usr/bin/env python3
import sqlite3,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
db=root/'03_Data_Release/database/haplod_v1.1.sqlite'
con=sqlite3.connect(db); c=con.cursor()
assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
expected={'track_points':18981,'track_summary':632,'catalogue_membership':745,'event_catalogue':1073,'impmct_era5_track_points':49435,'impmct_cloud_features':16001,'rojo_raw_observations':3850}
for t,n in expected.items():
 g=c.execute(f'select count(*) from {t}').fetchone()[0]; assert g==n,(t,g,n)
assert c.execute('select count(*) from track_summary where passes_all_stoll_criteria=1').fetchone()[0]==346
assert c.execute('select count(*)-count(distinct canonical_track_id||"|"||time) from track_points').fetchone()[0]==0
assert c.execute('select count(*) from track_points where lat not between -90 and 90 or lon not between -180 and 180').fetchone()[0]==0
assert c.execute("select count(*) from event_catalogue where lat not between -90 and 90 or lon not between -180 and 180").fetchone()[0]==0
assert c.execute("select count(*) from event_catalogue where source='Farjami_Kazemi_2024' and hemisphere!='SH'").fetchone()[0]==0
assert c.execute("select min(event_date),max(event_date) from event_catalogue where source='Farjami_Kazemi_2024'").fetchone()==('2000-03-09','2020-11-17')
print('HAPLoD v1.1 validation: PASS')
