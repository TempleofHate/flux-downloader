import os
import time
import random
import json
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

# ==================== CONFIGURAÇÕES INICIAIS ====================
app = Flask(__name__)

# Configurações da aplicação
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Diretórios
DOWNLOADS_DIR = Path('temp_downloads')
DOWNLOADS_DIR.mkdir(exist_ok=True)
COOKIES_FILE = 'cookies.txt'

# Cache para informações de vídeo
video_info_cache = {}
CACHE_DURATION = 300

# Controle de rate limiting
request_times = {}
RATE_LIMIT = 5

# ==================== FUNÇÕES AUXILIARES ====================
def format_duration(seconds):
    """Formata duração em segundos para HH:MM:SS"""
    if not seconds:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def clean_filename(filename):
    """Limpa caracteres inválidos de nomes de arquivo"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:200]

def get_random_user_agent():
    """Retorna um User-Agent aleatório"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    ]
    return random.choice(agents)

def check_rate_limit(ip):
    """Implementa rate limiting por IP"""
    now = time.time()
    if ip in request_times:
        request_times[ip] = [t for t in request_times[ip] if now - t < 60]
        if len(request_times[ip]) >= RATE_LIMIT:
            return False
        request_times[ip].append(now)
    else:
        request_times[ip] = [now]
    return True

def get_ydl_config(strategy_name="default", format_type="mp4", quality="medium"):
    """Retorna configuração do yt-dlp baseada na estratégia"""
    
    base_config = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'no_color': True,
        'socket_timeout': 30,
        'extract_timeout': 180,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ratelimit': 1024 * 1024,
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        },
        'outtmpl': str(DOWNLOADS_DIR / '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'continuedl': True,
        'noprogress': True,
        'geo_bypass': True,
    }
    
    if os.path.exists(COOKIES_FILE):
        base_config['cookiefile'] = COOKIES_FILE
    
    if strategy_name == "android":
        base_config['extractor_args'] = {
            'youtube': {'player_client': ['android']}
        }
        base_config['http_headers']['User-Agent'] = 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36'
    elif strategy_name == "ios":
        base_config['extractor_args'] = {
            'youtube': {'player_client': ['ios']}
        }
        base_config['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6) AppleWebKit/605.1.15'
    
    if format_type == "mp4":
        if quality == "high":
            base_config['format'] = 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]'
            base_config['merge_output_format'] = 'mp4'
        elif quality == "medium":
            base_config['format'] = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]'
            base_config['merge_output_format'] = 'mp4'
        else:
            base_config['format'] = 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]'
            base_config['merge_output_format'] = 'mp4'
    else:
        base_config['format'] = 'bestaudio/best'
        base_config['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    return base_config

def cleanup_old_files():
    """Remove arquivos com mais de 1 hora"""
    try:
        now = time.time()
        for file in DOWNLOADS_DIR.glob('*'):
            if file.is_file():
                file_age = now - file.stat().st_mtime
                if file_age > 3600:
                    try:
                        file.unlink()
                    except:
                        pass
    except:
        pass

# ==================== ROTAS CORRIGIDAS ====================

# ROTA PRINCIPAL - ACEITA GET E POST
@app.route('/', methods=['GET', 'POST'])
def index():
    """Página principal - aceita GET para carregar e POST para preview"""
    if request.method == 'GET':
        return render_template('index.html')
    
    # Se for POST (formulário tradicional)
    elif request.method == 'POST':
        try:
            url = request.form.get('url', '').strip()
            if not url:
                return render_template('index.html', error="URL não fornecida")
            
            # Verificar cache
            cache_key = f"preview_{hash(url)}"
            if cache_key in video_info_cache:
                cache_data, cache_time = video_info_cache[cache_key]
                if time.time() - cache_time < CACHE_DURATION:
                    return render_template('index.html', 
                                         show_download=True,
                                         video_info=cache_data,
                                         url=url)
            
            # Estratégias de extração
            strategies = ['web', 'android', 'ios']
            video_data = None
            
            for strategy in strategies:
                try:
                    ydl_config = get_ydl_config(strategy)
                    ydl_config['extract_flat'] = True
                    
                    with yt_dlp.YoutubeDL(ydl_config) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        video_data = {
                            'title': info.get('title', 'Sem título'),
                            'duration': info.get('duration', 0),
                            'duration_str': format_duration(info.get('duration', 0)),
                            'thumbnail': info.get('thumbnail', ''),
                            'channel': info.get('channel', 'Canal desconhecido'),
                            'views': info.get('view_count', 0),
                        }
                        
                        video_info_cache[cache_key] = (video_data, time.time())
                        break
                        
                except:
                    continue
            
            if video_data:
                return render_template('index.html', 
                                     show_download=True,
                                     video_info=video_data,
                                     url=url)
            else:
                return render_template('index.html', 
                                     error="Não foi possível obter informações do vídeo")
                
        except Exception as e:
            return render_template('index.html', 
                                 error=f"Erro: {str(e)}")

# ROTA DE DOWNLOAD - SOMENTE POST
@app.route('/download', methods=['POST'])
def download():
    """Processa download do vídeo (formulário tradicional)"""
    try:
        url = request.form.get('url', '').strip()
        format_type = request.form.get('format', 'mp4')
        quality = request.form.get('quality', 'medium')
        
        if not url:
            return render_template('index.html', error="URL não fornecida")
        
        # Estratégias de download
        strategies = ['web', 'android', 'ios']
        download_success = False
        filename = None
        video_title = None
        
        for strategy in strategies:
            try:
                ydl_config = get_ydl_config(strategy, format_type, quality)
                
                with yt_dlp.YoutubeDL(ydl_config) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_title = clean_filename(info.get('title', 'video'))
                    
                    if format_type == 'mp4':
                        filename = f"{video_title}.mp4"
                    else:
                        filename = f"{video_title}.mp3"
                    
                    filepath = DOWNLOADS_DIR / filename
                    ydl_config['outtmpl'] = str(filepath.with_suffix(''))
                    
                    ydl.download([url])
                    download_success = True
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if 'Sign in to confirm' in error_msg:
                    continue
                else:
                    return render_template('index.html', 
                                         error=f"Erro no download: {error_msg}")
        
        if download_success and filename and filepath.exists():
            # Iniciar limpeza em background
            threading.Thread(target=cleanup_old_files, daemon=True).start()
            
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename
            )
        else:
            return render_template('index.html', 
                                 error="Falha no download. YouTube pode estar bloqueando.")
            
    except Exception as e:
        return render_template('index.html', 
                             error=f"Erro interno: {str(e)}")

# ==================== API ENDPOINTS ====================
@app.route('/api/preview', methods=['POST'])
def api_preview():
    """API para pré-visualizar vídeo"""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({'error': 'Muitas requisições'}), 429
        
        data = request.get_json()
        if not data:
            data = request.form
        
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        # Verificar cache
        cache_key = f"preview_{hash(url)}"
        if cache_key in video_info_cache:
            cache_data, cache_time = video_info_cache[cache_key]
            if time.time() - cache_time < CACHE_DURATION:
                return jsonify(cache_data)
        
        # Extrair informações
        strategies = ['web', 'android', 'ios']
        
        for strategy in strategies:
            try:
                ydl_config = get_ydl_config(strategy)
                ydl_config['extract_flat'] = True
                
                with yt_dlp.YoutubeDL(ydl_config) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    video_data = {
                        'title': info.get('title', 'Sem título'),
                        'duration': info.get('duration', 0),
                        'duration_str': format_duration(info.get('duration', 0)),
                        'thumbnail': info.get('thumbnail', ''),
                        'channel': info.get('channel', 'Canal desconhecido'),
                        'views': info.get('view_count', 0),
                        'success': True
                    }
                    
                    video_info_cache[cache_key] = (video_data, time.time())
                    return jsonify(video_data)
                    
            except:
                continue
        
        return jsonify({'error': 'Não foi possível obter informações'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """API para processar download"""
    try:
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({'error': 'Muitas requisições'}), 429
        
        data = request.get_json()
        if not data:
            data = request.form
        
        url = data.get('url', '').strip()
        format_type = data.get('format', 'mp4')
        quality = data.get('quality', 'medium')
        
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        # Estratégias de download
        strategies = ['web', 'android', 'ios']
        
        for strategy in strategies:
            try:
                ydl_config = get_ydl_config(strategy, format_type, quality)
                
                with yt_dlp.YoutubeDL(ydl_config) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_title = clean_filename(info.get('title', 'video'))
                    
                    if format_type == 'mp4':
                        filename = f"{video_title}.mp4"
                    else:
                        filename = f"{video_title}.mp3"
                    
                    filepath = DOWNLOADS_DIR / filename
                    ydl_config['outtmpl'] = str(filepath.with_suffix(''))
                    
                    ydl.download([url])
                    
                    download_info = {
                        'success': True,
                        'filename': filename,
                        'title': info.get('title', 'video'),
                        'filesize': os.path.getsize(filepath) if filepath.exists() else 0,
                        'strategy_used': strategy,
                        'has_cookies': os.path.exists(COOKIES_FILE)
                    }
                    
                    return jsonify(download_info)
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if 'Sign in to confirm' in error_msg:
                    continue
                else:
                    return jsonify({'error': f'Erro: {error_msg}'}), 500
            except:
                continue
        
        return jsonify({'error': 'Todas as estratégias falharam'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/file/<filename>', methods=['GET'])
def api_get_file(filename):
    """API para baixar arquivo"""
    try:
        if '..' in filename or '/' in filename:
            return jsonify({'error': 'Nome de arquivo inválido'}), 400
        
        filepath = DOWNLOADS_DIR / filename
        
        if not filepath.exists():
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
        
        # Limpar arquivo após servir
        def remove_file():
            time.sleep(60)
            try:
                if filepath.exists():
                    filepath.unlink()
            except:
                pass
        
        threading.Thread(target=remove_file, daemon=True).start()
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Erro: {str(e)}'}), 500

# ==================== ROTAS AUXILIARES ====================
@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(video_info_cache)
    })

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('index.html', error="Página não encontrada"), 404

@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 errors"""
    return render_template('index.html', error="Método não permitido"), 405

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return render_template('index.html', error="Erro interno do servidor"), 500

# ==================== INICIALIZAÇÃO ====================
if __name__ == '__main__':
    # Iniciar limpeza periódica
    def periodic_cleanup():
        while True:
            time.sleep(3600)
            cleanup_old_files()
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    # Configurações do servidor
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Servidor iniciado na porta {port}")
    print(f"📁 Downloads dir: {DOWNLOADS_DIR}")
    print(f"🍪 Cookies: {os.path.exists(COOKIES_FILE)}")
    
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)