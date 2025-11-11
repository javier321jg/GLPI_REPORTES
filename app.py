import os, io, csv, unicodedata, traceback, logging
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

# ------------------------- Utilidades -------------------------
def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def _canon(name: str) -> str:
    """Normaliza encabezados: minúsculas, sin acentos, guiones bajos."""
    name = _strip_accents(str(name)).lower().strip()
    for ch in ['-', '/', '.', '(', ')']:
        name = name.replace(ch, ' ')
    name = '_'.join(name.split())
    return name

COLUMN_ALIASES = {
    # clave canónica -> posibles encabezados normalizados
    'id': {
        'id', 'id_ticket', 'ticket', 'numero', 'nro', 'nro_ticket', 'folio', 'codigo'
    },
    'fecha': {
        'fecha', 'fecha_de_apertura', 'fecha_apertura', 'apertura', 'fechacreacion', 'creado', 'created_at'
    },
    'estado': {
        'estado', 'estados', 'status'
    },
    'prioridad': {
        'prioridad', 'priority'
    },
    'tecnico': {
        'asignado_a_tecnico', 'asignado_a_-_tecnico', 'tecnico', 'asignado', 'agente', 'responsable'
    },
    'categoria': {
        'categoria', 'categoria_', 'categorias', 'category'
    }
}

DATE_FORMATS = [
    "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M",
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"
]

def clean_for_json(obj):
    try:
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_for_json(x) for x in obj]
        if isinstance(obj, (pd.Index, pd.RangeIndex)):
            return list(obj)
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if pd.isna(obj):
            return None
        return obj
    except Exception:
        logger.exception("clean_for_json")
        return None

def _infer_delimiter(sample: bytes) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample.decode('utf-8', 'ignore'), delimiters=";,|\t,")
        return dialect.delimiter
    except Exception:
        return ';' if b';' in sample else ','

def _read_csv_flex(fp: str) -> pd.DataFrame:
    """Lee CSV con auto-delimiter y fallback de encoding."""
    for enc in ('utf-8', 'latin-1'):
        try:
            with open(fp, 'rb') as f:
                head = f.read(4096)
            delim = _infer_delimiter(head)
            df = pd.read_csv(fp, sep=delim, encoding=enc, engine='python')
            if df.shape[1] == 1 and df.columns[0] and delim != ',':
                # intentar coma si sólo tomó una columna
                df = pd.read_csv(fp, sep=',', encoding=enc, engine='python')
            return df
        except Exception:
            continue
    # último intento de pandas infer
    return pd.read_csv(fp, sep=None, engine='python')

def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mapea encabezados reales -> canónicos soportando alias y tildes."""
    original_cols = list(df.columns)
    norm_map = {_canon(c): c for c in df.columns}

    mapped = {}
    for canon, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in norm_map:
                found = norm_map[alias]
                break
        if found is None:
            # si falta ID, generamos incremental; otras pueden quedar nulas
            if canon == 'id':
                df['__auto_id__'] = range(1, len(df) + 1)
                mapped[canon] = '__auto_id__'
            else:
                mapped[canon] = None
        else:
            mapped[canon] = found

    # renombrar a canónicos cuando existan
    rename_dict = {mapped[k]: k for k in mapped if mapped[k] is not None}
    df = df.rename(columns=rename_dict)

    # asegurar columnas canónicas
    for k in COLUMN_ALIASES.keys():
        if k not in df.columns:
            df[k] = np.nan

    # fecha -> datetime robusto
    if df['fecha'].notna().any():
        # intento masivo con dayfirst=True
        dt = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True, infer_datetime_format=True)
        # rellenar los NaT probando formatos manuales
        if dt.isna().any():
            raw = df['fecha'].astype(str)
            parsed = []
            for val in raw:
                val = val.strip()
                ok = None
                for fmt in DATE_FORMATS:
                    try:
                        ok = datetime.strptime(val, fmt)
                        break
                    except Exception:
                        continue
                parsed.append(ok)
            dt2 = pd.to_datetime(parsed, errors='coerce')
            dt = dt.fillna(dt2)
        df['fecha'] = dt

    # normalizaciones de texto
    for col in ('estado', 'prioridad', 'tecnico', 'categoria'):
        df[col] = df[col].astype(str).replace({'nan': None})
        df[col] = df[col].apply(lambda x: None if x in (None, '', 'None') else x)

    # métricas derivadas
    df['anio'] = df['fecha'].dt.year
    df['mes_nombre'] = df['fecha'].dt.month_name(locale='es_ES') if hasattr(pd, 'options') else df['fecha'].dt.month_name()
    df['mes_anio'] = df['fecha'].dt.strftime('%Y-%m')

    # Log de mapeo para depuración
    logger.info("Columnas originales: %s", original_cols)
    logger.info("Columnas canónicas presentes: %s", list(df.columns))
    return df

# ------------------------- Analizador -------------------------
class GLPIAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = _map_columns(df).copy()
        self._fill_defaults()

    def _fill_defaults(self):
        if self.df.empty:
            return
        self.df['estado'] = self.df['estado'].fillna('Sin Estado')
        self.df['prioridad'] = self.df['prioridad'].fillna('Normal')
        self.df['tecnico'] = self.df['tecnico'].fillna('Sin Asignar')
        self.df['categoria'] = self.df['categoria'].fillna('Sin Categoría')
        if 'id' in self.df.columns:
            self.df['id'] = pd.to_numeric(self.df['id'], errors='coerce').fillna(0).astype(int)

    def dashboard_stats(self):
        if self.df.empty:
            return {
                'total_tickets': 0,
                'total_tecnicos': 0,
                'tickets_por_estado': {},
                'tickets_por_prioridad': {},
                'tickets_por_categoria': {},
                'tendencia_mensual': {},
                'top_tecnicos': {}
            }

        total_tickets = len(self.df)
        total_tecnicos = self.df['tecnico'].nunique()
        tickets_por_estado = self.df['estado'].value_counts(dropna=False).to_dict()
        tickets_por_prioridad = self.df['prioridad'].value_counts(dropna=False).to_dict()
        tickets_por_categoria = self.df['categoria'].value_counts(dropna=False).to_dict()

        # Tendencia por mes-año: contar por mes_anio
        tendencia_mensual = (
            self.df.dropna(subset=['mes_anio'])
                   .groupby('mes_anio')['id'].count()
                   .sort_index()
                   .to_dict()
        )

        top_tecnicos = (
            self.df.groupby('tecnico')['id']
                   .count()
                   .sort_values(ascending=False)
                   .head(10)
                   .to_dict()
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
        if self.df.empty:
            return []
        # Conteo por técnico y mes_nombre
        tmp = self.df.copy()
        tmp['mes_nombre'] = tmp['fecha'].dt.month_name(locale='es_ES') if hasattr(pd, 'options') else tmp['fecha'].dt.month_name()
        monthly = tmp.groupby(['tecnico', 'mes_nombre'])['id'].count().reset_index()
        pivot = monthly.pivot_table(index='tecnico', columns='mes_nombre', values='id', fill_value=0)
        result = []
        for tech in pivot.index:
            row = {'Técnico': str(tech)}
            for col in sorted(pivot.columns, key=lambda m: m.lower()):
                row[str(col)] = int(pivot.loc[tech, col])
            result.append(row)
        return result

    def filter_tickets(self, filter_type: str, filter_value: str):
        if self.df.empty:
            return []
        df = self.df.copy()
        if filter_type == 'category':
            df = df[df['categoria'] == filter_value]
        elif filter_type == 'status':
            df = df[df['estado'] == filter_value]
        elif filter_type == 'tech':
            df = df[df['tecnico'] == filter_value]
        elif filter_type == 'month':
            # acepta 'YYYY-MM' o nombre de mes en español
            mask = (df['mes_anio'] == filter_value) | (df['mes_nombre'] == filter_value)
            df = df[mask]
        elif filter_type == 'pending':
            df = df[df['estado'].str.lower() == 'pendiente']
        elif filter_type == 'efficiency':
            df = df[df['estado'].str.lower() == 'resuelto']

        # columnas de salida amigables
        out = df[['id', 'fecha', 'estado', 'prioridad', 'tecnico', 'categoria']].copy()
        out = out.rename(columns={
            'id': 'ID',
            'fecha': 'Fecha',
            'estado': 'Estado',
            'prioridad': 'Prioridad',
            'tecnico': 'Tecnico',
            'categoria': 'Categoria'
        })
        return clean_for_json(out.to_dict('records'))

    def ticket_details(self, ticket_id: int):
        if self.df.empty:
            return None
        row = self.df[self.df['id'] == int(ticket_id)]
        if row.empty:
            return None
        out = row.iloc[0][['id', 'fecha', 'estado', 'prioridad', 'tecnico', 'categoria']].rename({
            'id': 'ID',
            'fecha': 'Fecha',
            'estado': 'Estado',
            'prioridad': 'Prioridad',
            'tecnico': 'Tecnico',
            'categoria': 'Categoria'
        })
        return clean_for_json(out.to_dict())

# ------------------------- Rutas -------------------------
@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')

@app.route('/ticket-details.html')
def ticket_details_page():
    return render_template('ticket-details.html')

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint no encontrado', 'path': request.path}), 404
    try:
        return render_template('index.html')
    except Exception:
        return jsonify({'success': False, 'error': 'Página no encontrada'}), 404

@app.route('/api/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'error': 'No selected file'}), 400

        fname = secure_filename(file.filename)
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(fpath)

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
            try:
                os.remove(fpath)
            except Exception:
                pass
    except Exception as ex:
        logger.exception("upload")
        return jsonify({'success': False, 'error': str(ex)}), 500

@app.route('/api/tickets/filter')
def filter_tickets():
    try:
        ftype = request.args.get('type')
        fvalue = request.args.get('value')
        if not ftype or (ftype not in {'pending', 'efficiency'} and not fvalue):
            return jsonify({'success': False, 'error': 'Parámetros incompletos'}), 400
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400

        data = app.current_analyzer.filter_tickets(ftype, fvalue)
        return jsonify({'success': True, 'data': {'tickets': data, 'total': len(data)}})
    except Exception as ex:
        logger.exception("filter_tickets")
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
        logger.exception("get_ticket")
        return jsonify({'success': False, 'error': str(ex)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
