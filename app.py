import os, csv, unicodedata, logging, traceback
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("glpi")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------- Utilidades ----------
MESES_ES = {
    1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
    7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"
}

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c))

def _canon(name: str) -> str:
    name = _strip_accents(name).lower().strip()
    for ch in ['-', '/', '.', '(', ')']:
        name = name.replace(ch, ' ')
    return '_'.join(name.split())

COLUMN_ALIASES = {
    'id': {'id','id_ticket','ticket','numero','nro','nro_ticket','folio','codigo'},
    'fecha': {'fecha','fecha_de_apertura','fecha_apertura','apertura','fechacreacion','creado','created_at','datetime','date'},
    'estado': {'estado','estados','status'},
    'prioridad': {'prioridad','priority'},
    'tecnico': {'asignado_a_tecnico','asignado_a_-_tecnico','tecnico','asignado','agente','responsable'},
    'categoria': {'categoria','categorias','category'}
}

DATE_FORMATS = [
    "%d-%m-%Y %H:%M","%d/%m/%Y %H:%M","%Y-%m-%d %H:%M",
    "%d-%m-%Y","%d/%m/%Y","%Y-%m-%d","%m/%d/%Y"
]

def clean_for_json(obj):
    try:
        if isinstance(obj, dict):      return {k: clean_for_json(v) for k,v in obj.items()}
        if isinstance(obj, list):      return [clean_for_json(x) for x in obj]
        if isinstance(obj, (pd.Index, pd.RangeIndex)): return list(obj)
        if isinstance(obj, pd.Series): return obj.to_dict()
        if isinstance(obj, np.integer):return int(obj)
        if isinstance(obj, np.floating):return float(obj)
        if pd.isna(obj):               return None
        return obj
    except Exception:
        logger.exception("clean_for_json")
        return None

def _infer_delimiter(sample: bytes) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample.decode('utf-8','ignore'), delimiters=";,|\t,")
        return dialect.delimiter
    except Exception:
        return ';' if b';' in sample else ','

def _read_csv_flex(fp: str) -> pd.DataFrame:
    for enc in ('utf-8','latin-1'):
        try:
            with open(fp,'rb') as f: head = f.read(4096)
            delim = _infer_delimiter(head)
            df = pd.read_csv(fp, sep=delim, encoding=enc, engine='python')
            if df.shape[1]==1 and delim!=',':
                df = pd.read_csv(fp, sep=',', encoding=enc, engine='python')
            return df
        except Exception:
            continue
    return pd.read_csv(fp, sep=None, engine='python')

def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    norm_map = {_canon(c): c for c in df.columns}
    mapped = {}
    for canon, aliases in COLUMN_ALIASES.items():
        found = None
        for a in aliases:
            if a in norm_map:
                found = norm_map[a]
                break
        if found is None:
            if canon == 'id':
                df['__auto_id__'] = range(1, len(df)+1)
                mapped[canon] = '__auto_id__'
            else:
                mapped[canon] = None
        else:
            mapped[canon] = found

    rename = {mapped[k]: k for k in mapped if mapped[k] is not None}
    df = df.rename(columns=rename)

    for k in COLUMN_ALIASES.keys():
        if k not in df.columns:
            df[k] = np.nan

    # fechas robustas sin locale
    if df['fecha'].notna().any():
        dt = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True, infer_datetime_format=True)
        if dt.isna().any():
            parsed = []
            for val in df['fecha'].astype(str):
                val = val.strip()
                ok = None
                for fmt in DATE_FORMATS:
                    try:
                        ok = datetime.strptime(val, fmt); break
                    except Exception:
                        continue
                parsed.append(ok)
            dt2 = pd.to_datetime(parsed, errors='coerce')
            dt = dt.fillna(dt2)
        df['fecha'] = dt

    for col in ('estado','prioridad','tecnico','categoria'):
        df[col] = df[col].astype(str).replace({'nan': None})
        df[col] = df[col].apply(lambda x: None if x in (None,'','None') else x)

    df['anio'] = df['fecha'].dt.year
    df['mes']  = df['fecha'].dt.month
    df['mes_nombre'] = df['mes'].map(MESES_ES)
    df['mes_anio'] = df['fecha'].dt.strftime('%Y-%m')

    logger.info("Columnas canónicas: %s", list(df.columns))
    return df

# ---------- Analizador ----------
class GLPIAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = _map_columns(df).copy()
        self._fill_defaults()

    def _fill_defaults(self):
        if self.df.empty: return
        self.df['estado']    = self.df['estado'].fillna('Sin Estado')
        self.df['prioridad'] = self.df['prioridad'].fillna('Normal')
        self.df['tecnico']   = self.df['tecnico'].fillna('Desarrollo o Mesa de Ayuda')
        self.df['categoria'] = self.df['categoria'].fillna('Sin Categoría')
        self.df['id']        = pd.to_numeric(self.df['id'], errors='coerce').fillna(0).astype(int)

    def dashboard_stats(self):
        if self.df.empty:
            return {'total_tickets':0,'total_tecnicos':0,'tickets_por_estado':{},
                    'tickets_por_prioridad':{},'tickets_por_categoria':{},
                    'tendencia_mensual':{},'top_tecnicos':{}}

        total_tickets = len(self.df)
        total_tecnicos = self.df['tecnico'].nunique()
        tickets_por_estado    = self.df['estado'].value_counts(dropna=False).to_dict()
        tickets_por_prioridad = self.df['prioridad'].value_counts(dropna=False).to_dict()
        tickets_por_categoria = self.df['categoria'].value_counts(dropna=False).to_dict()
        tendencia_mensual = (
            self.df.dropna(subset=['mes_anio'])
                   .groupby('mes_anio')['id'].count()
                   .sort_index()
                   .to_dict()
        )
        top_tecnicos = (
            self.df.groupby('tecnico')['id'].count()
                   .sort_values(ascending=False).head(10).to_dict()
        )
        return clean_for_json({
            'total_tickets': total_tickets,
            'total_tecnicos': total_tecnicos,
            'tickets_por_estado': tickets_por_estado,
            'tickets_por_prioridad': tickets_por_prioridad,
            'tickets_por_categoria': tickets_por_categoria,
            'tendencia_mensual': tendencia_mensual,
            'top_tecnicos': top_tecnicos
        })

    def technician_monthly_stats(self):
        if self.df.empty: return []
        g = self.df.groupby(['tecnico','mes_nombre'])['id'].count().reset_index()
        p = g.pivot_table(index='tecnico', columns='mes_nombre', values='id', fill_value=0)
        result = []
        for tech in p.index:
            row = {'Técnico': str(tech)}
            for m in sorted(p.columns, key=lambda x: x or ''):
                row[m] = int(p.loc[tech, m])
            result.append(row)
        return result

    def technician_daily_stats(self):
        """Retorna estadísticas de tickets por técnico por día agrupados por año-mes"""
        if self.df.empty: return []
        
        df_copy = self.df.copy()
        df_copy['anio'] = df_copy['fecha'].dt.year
        df_copy['mes'] = df_copy['fecha'].dt.month
        df_copy['mes_nombre'] = df_copy['mes'].map(MESES_ES)
        df_copy['dia'] = df_copy['fecha'].dt.day
        df_copy['anio_mes'] = df_copy['anio'].astype(str) + '-' + df_copy['mes_nombre']
        df_copy['anio_mes_dia'] = df_copy['anio_mes'] + '-' + df_copy['dia'].astype(str)
        
        # Agrupar por técnico y año-mes-día
        g = df_copy.groupby(['tecnico', 'anio_mes', 'dia'])['id'].count().reset_index()
        
        # Crear estructura jerárquica
        result = []
        tecnicos = g['tecnico'].unique()
        
        for tech in tecnicos:
            tech_data = g[g['tecnico'] == tech]
            row = {'Técnico': str(tech)}
            
            # Agrupar por año-mes
            for anio_mes in sorted(tech_data['anio_mes'].unique()):
                mes_data = tech_data[tech_data['anio_mes'] == anio_mes]
                for _, row_data in mes_data.iterrows():
                    dia = str(int(row_data['dia']))
                    col_name = f"{anio_mes}|{dia}"
                    row[col_name] = int(row_data['id'])
            
            result.append(row)
        
        return result
    def filter_tickets(self, ftype: str, fvalue: str):
        if self.df.empty: return []
        df = self.df.copy()
        if ftype == 'category':   df = df[df['categoria'] == fvalue]
        elif ftype == 'status':   df = df[df['estado'] == fvalue]
        elif ftype == 'tech':     df = df[df['tecnico'] == fvalue]
        elif ftype == 'month':    df = df[(df['mes_anio'] == fvalue) | (df['mes_nombre'] == fvalue)]
        elif ftype == 'pending':  df = df[df['estado'].str.lower() == 'pendiente']
        elif ftype == 'efficiency': df = df[df['estado'].str.lower() == 'resuelto']
        out = df[['id','fecha','estado','prioridad','tecnico','categoria']].rename(columns={
            'id':'ID','fecha':'Fecha','estado':'Estado','prioridad':'Prioridad','tecnico':'Tecnico','categoria':'Categoria'
        })
        return clean_for_json(out.to_dict('records'))

    def ticket_details(self, ticket_id:int):
        if self.df.empty: return None
        row = self.df[self.df['id'] == int(ticket_id)]
        if row.empty: return None
        r = row.iloc[0][['id','fecha','estado','prioridad','tecnico','categoria']].rename({
            'id':'ID','fecha':'Fecha','estado':'Estado','prioridad':'Prioridad','tecnico':'Tecnico','categoria':'Categoria'
        })
        return clean_for_json(r.to_dict())

# ---------- Rutas ----------
@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
        f = request.files['file']
        if not f.filename:
            return jsonify({'success': False, 'error': 'No selected file'}), 400

        fname = secure_filename(f.filename)
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        f.save(fpath)

        try:
            df = _read_csv_flex(fpath)
            if df.empty:
                return jsonify({'success': False, 'error': 'CSV vacío'}), 400
            analyzer = GLPIAnalyzer(df)
            app.current_analyzer = analyzer
            payload = {
                'technician_stats': analyzer.technician_monthly_stats(),
                'dashboard_stats': analyzer.dashboard_stats()
            }
            return jsonify({'success': True, 'data': clean_for_json(payload)})
        finally:
            try: os.remove(fpath)
            except Exception: pass
    except Exception as ex:
        logger.error("upload failed: %s", ex)
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/tickets/filter')
def filter_tickets():
    try:
        ftype = request.args.get('type')
        fvalue = request.args.get('value')
        if not ftype or (ftype not in {'pending','efficiency'} and not fvalue):
            return jsonify({'success': False, 'error': 'Parámetros incompletos'}), 400
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400
        data = app.current_analyzer.filter_tickets(ftype, fvalue)
        return jsonify({'success': True, 'data': {'tickets': data, 'total': len(data)}})
    except Exception as ex:
        logger.error("filter error: %s", ex)
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/tickets/<int:ticket_id>')
def get_ticket(ticket_id: int):
    try:
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400
        t = app.current_analyzer.ticket_details(ticket_id)
        if not t:
            return jsonify({'success': False, 'error': 'Ticket not found'}), 404
        return jsonify({'success': True, 'data': {'ticket': t}})
    except Exception as ex:
        logger.error("get_ticket error: %s", ex)
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/daily-report')
def daily_report():
    try:
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400
        data = app.current_analyzer.technician_daily_stats()
        return jsonify({'success': True, 'data': {'daily_stats': data}})
    except Exception as ex:
        logger.error("daily_report error: %s", ex)
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint no encontrado', 'path': request.path}), 404
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
