import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from flask_cors import CORS
import traceback

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app)

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rutas de carpeta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

def clean_for_json(obj):
    """Limpia objetos para que sean serializables en JSON."""
    try:
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(x) for x in obj]
        elif isinstance(obj, (pd.Index, pd.RangeIndex)):
            return list(obj)
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif pd.isna(obj):
            return None
        return obj
    except Exception as e:
        logger.error(f"Error en clean_for_json: {str(e)}")
        logger.error(traceback.format_exc())
        return None


class GLPIAnalyzer:
    def __init__(self, df):
        self.df = df
        self.process_dataframe()

    def process_dataframe(self):
        """Procesa el DataFrame inicial: convierte fechas, añade columnas de mes/año, etc."""
        try:
            logger.info("Iniciando procesamiento del DataFrame")
            
            # Convertir la columna 'Fecha de apertura' a tipo fecha
            self.df['Fecha de apertura'] = pd.to_datetime(
                self.df['Fecha de apertura'],
                format='%d-%m-%Y %H:%M',
                errors='coerce'
            )

            # Extraer Mes y Año
            self.df['Mes'] = self.df['Fecha de apertura'].dt.strftime('%B')
            self.df['Año'] = self.df['Fecha de apertura'].dt.year
            self.df['Mes_Año'] = self.df['Fecha de apertura'].dt.strftime('%Y-%m')

            # Llenar nulos
            self.df = self.df.fillna({
                'Estados': 'Sin Estado',
                'Prioridad': 'Normal',
                'Asignado a - Técnico': 'Sin Asignar',
                'Categoría': 'Sin Categoría',
                'ID': 0
            })

            logger.info("DataFrame procesado exitosamente")
        except Exception as e:
            logger.error(f"Error en process_dataframe: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_technician_monthly_stats(self):
        """Devuelve la lista de diccionarios con tickets por Técnico y Mes."""
        try:
            if self.df.empty:
                logger.warning("DataFrame está vacío")
                return []

            monthly_stats = self.df.groupby(['Asignado a - Técnico', 'Mes'])['ID'].count().reset_index()

            # Crear pivot table con filas = técnico, columnas = mes
            pivot_data = pd.pivot_table(
                monthly_stats,
                values='ID',
                index=['Asignado a - Técnico'],
                columns=['Mes'],
                fill_value=0
            )

            # Convertir a lista de diccionarios para el frontend
            result = []
            for idx in pivot_data.index:
                row_dict = {'Técnico': str(idx)}
                for col in pivot_data.columns:
                    row_dict[str(col)] = int(pivot_data.loc[idx, col])
                result.append(row_dict)
            return result

        except Exception as e:
            logger.error(f"Error en get_technician_monthly_stats: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_dashboard_stats(self):
        """
        Genera estadísticas generales: 
        - total_tickets
        - total_tecnicos
        - tickets_por_estado
        - tickets_por_prioridad
        - tickets_por_categoria
        - tendencia_mensual
        - top_tecnicos
        """
        try:
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
            
            # Contar tickets totales, etc.
            total_tickets = len(self.df)
            total_tecnicos = self.df['Asignado a - Técnico'].nunique()
            tickets_por_estado = self.df['Estados'].value_counts().to_dict()
            tickets_por_prioridad = self.df['Prioridad'].value_counts().to_dict()
            tickets_por_categoria = self.df['Categoría'].value_counts().to_dict()
            tendencia_mensual = self.df.groupby('Mes_Año')['ID'].count().to_dict()
            
            # Top 10 técnicos con más tickets
            top_tec = (
                self.df.groupby('Asignado a - Técnico')['ID']
                .count()
                .sort_values(ascending=False)
                .head(10)
                .to_dict()
            )

            stats = {
                'total_tickets': total_tickets,
                'total_tecnicos': total_tecnicos,
                'tickets_por_estado': tickets_por_estado,
                'tickets_por_prioridad': tickets_por_prioridad,
                'tickets_por_categoria': tickets_por_categoria,
                'tendencia_mensual': tendencia_mensual,
                'top_tecnicos': top_tec
            }

            return clean_for_json(stats)

        except Exception as e:
            logger.error(f"Error en get_dashboard_stats: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_tickets_by_filter(self, filter_type, filter_value):
        """
        Obtiene tickets filtrados según diferentes criterios
        """
        try:
            if self.df.empty:
                return []
                
            filtered_df = self.df.copy()
            
            if filter_type == 'category':
                filtered_df = filtered_df[filtered_df['Categoría'] == filter_value]
            elif filter_type == 'status':
                filtered_df = filtered_df[filtered_df['Estados'] == filter_value]
            elif filter_type == 'tech':
                filtered_df = filtered_df[filtered_df['Asignado a - Técnico'] == filter_value]
            elif filter_type == 'month':
                filtered_df = filtered_df[filtered_df['Mes_Año'] == filter_value]
            elif filter_type == 'pending':
                filtered_df = filtered_df[filtered_df['Estados'] == 'Pendiente']
            elif filter_type == 'efficiency':
                filtered_df = filtered_df[filtered_df['Estados'] == 'Resuelto']
            
            # Convertir a formato de lista de diccionarios para JSON
            tickets = filtered_df.to_dict('records')
            
            # Limpiar datos para JSON
            return clean_for_json(tickets)
            
        except Exception as e:
            logger.error(f"Error en get_tickets_by_filter: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_ticket_details(self, ticket_id):
        """
        Obtiene detalles de un ticket específico
        """
        try:
            if self.df.empty:
                return None
                
            ticket = self.df[self.df['ID'] == int(ticket_id)]
            if ticket.empty:
                return None
                
            return clean_for_json(ticket.iloc[0].to_dict())
            
        except Exception as e:
            logger.error(f"Error en get_ticket_details: {str(e)}")
            logger.error(traceback.format_exc())
            return None


@app.route('/')
def index():
    """Renderiza la plantilla base."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Endpoint al que el formulario JS hace POST con el CSV.
    Devuelve JSON con:
      - technician_stats
      - dashboard_stats
    """
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(filepath)
                # Leer el CSV con separador ';'
                df = pd.read_csv(filepath, sep=';', encoding='utf-8')

                if df.empty:
                    return jsonify({'success': False, 'error': 'El archivo CSV está vacío'}), 400
                
                # Guardar el analizador en la aplicación
                app.current_analyzer = GLPIAnalyzer(df)
                
                response_data = {
                    'success': True,
                    'data': {
                        'technician_stats': app.current_analyzer.get_technician_monthly_stats(),
                        'dashboard_stats': app.current_analyzer.get_dashboard_stats()
                    }
                }

                return jsonify(clean_for_json(response_data))

            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({'success': False, 'error': str(e)}), 500
            
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)

        return jsonify({'success': False, 'error': 'Invalid file'}), 400

    except Exception as e:
        logger.error(f"Error in upload_file: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/tickets/filter', methods=['GET'])
def filter_tickets():
    """
    Endpoint para filtrar tickets según diferentes criterios
    Parámetros URL: type (category, status, tech, month) y value
    """
    try:
        filter_type = request.args.get('type')
        filter_value = request.args.get('value')
        
        if not filter_type or not filter_value:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
            
        # Verificar si hay datos cargados
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400
            
        tickets = app.current_analyzer.get_tickets_by_filter(filter_type, filter_value)
        
        return jsonify({
            'success': True,
            'data': {
                'tickets': tickets,
                'total': len(tickets)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in filter_tickets: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
# Añade estas rutas después de la ruta '/'

@app.route('/ticket-details.html')
def ticket_details():
    """Renderiza la página de detalles de tickets"""
    return render_template('ticket-details.html')

@app.route('/index.html')
def index_html():
    """Ruta alternativa para index.html"""
    return render_template('index.html')

# Modifica el error handler 404 para que devuelva la página en lugar de JSON
@app.errorhandler(404)
def page_not_found(e):
    """Manejador personalizado para errores 404"""
    app.logger.error(f"Página no encontrada: {request.url}")
    # Si es una solicitud API, devolver JSON
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Endpoint no encontrado',
            'path': request.path
        }), 404
    # Si es una solicitud web normal, intentar renderizar la página
    try:
        if 'ticket-details.html' in request.path:
            return render_template('ticket-details.html')
        return render_template('index.html')
    except:
        return jsonify({
            'success': False,
            'error': 'Página no encontrada',
            'path': request.path
        }), 404

@app.route('/api/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    """
    Endpoint para obtener detalles de un ticket específico
    """
    try:
        if not hasattr(app, 'current_analyzer'):
            return jsonify({'success': False, 'error': 'No data loaded'}), 400
            
        ticket = app.current_analyzer.get_ticket_details(ticket_id)
        if not ticket:
            return jsonify({'success': False, 'error': 'Ticket not found'}), 404
            
        return jsonify({
            'success': True,
            'data': {'ticket': ticket}
        })
        
    except Exception as e:
        logger.error(f"Error in get_ticket: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)