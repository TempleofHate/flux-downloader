import os
import time
import random
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp

# ==================== CONFIGURAÇÕES INICIAIS ====================
app = Flask(__name__)

# Configurações da aplicação
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua-chave-secreta-aqui-mude-em-producao')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Diretórios
DOWNLOADS_DIR = Path('temp_downloads')
DOWNLOADS_DIR.mkdir(exist_ok=True)
COOKIES_FILE = 'cookies.txt'

# Cache para informações de vídeo (evita múltiplas requisições)
video_info_cache = {}
CACHE_DURATION = 300  # 5 minutos

# Controle de rate limiting
request_times = {}
RATE_LIMIT = 5  # Requisições por minuto

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
    return filename[:200]  # Limita tamanho

def get_random_user_agent():
    """Retorna um User-Agent aleatório para evitar detecção"""
    agents = [
        # Chrome - Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
        
        # Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        
        # Mobile
        'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    ]
    return random.choice(agents)

def check_rate_limit(ip):
    """Implementa rate limiting por IP"""
    now = time.time()
    if ip in request_times:
        # Remove requisições antigas (mais de 1 minuto)
        request_times[ip] = [t for t in request_times[ip] if now - t < 60]
        
        # Verifica se excedeu o limite
        if len(request_times[ip]) >= RATE_LIMIT:
            return False
        
        request_times[ip].append(now)
    else:
        request_times[ip] = [now]
    
    return True

def get_ydl_config(strategy_name="default", format_type="mp4", quality="medium"):
    """Retorna configuração do yt-dlp baseada na estratégia"""
    
    # Configuração base comum
    base_config = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'no_color': True,
        'socket_timeout': 30,
        'extract_timeout': 180,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ratelimit': 1024 * 1024,  # 1 MB/s
        'throttledratelimit': 0,
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        },
        'outtmpl': {
            'default': str(DOWNLOADS_DIR / '%(title)s.%(ext)s'),
            'chapter': str(DOWNLOADS_DIR / '%(title)s - %(section_number)s - %(section_title)s.%(ext)s'),
        },
        'restrictfilenames': True,
        'windowsfilenames': True,
        'continuedl': True,
        'noprogress': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'geo_bypass_ip_block': '0.0.0.0/0',
    }
    
    # Adicionar cookies se existirem
    if os.path.exists(COOKIES_FILE):
        base_config['cookiefile'] = COOKIES_FILE
        print(f"✅ Cookies carregados de {COOKIES_FILE}")
    
    # Estratégias específicas
    if strategy_name == "android":
        base_config['extractor_args'] = {
            'youtube': {
                'player_client': ['android'],
                'player_skip': ['configs', 'js'],
            }
        }
        base_config['http_headers']['User-Agent'] = 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    
    elif strategy_name == "ios":
        base_config['extractor_args'] = {
            'youtube': {
                'player_client': ['ios'],
                'player_skip': ['configs', 'js'],
            }
        }
        base_config['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
    
    elif strategy_name == "web":
        base_config['extractor_args'] = {
            'youtube': {
                'player_client': ['web'],
                'player_skip': ['configs'],
            }
        }
    
    # Configuração de formato baseado no tipo e qualidade
    if format_type == "mp4":
        if quality == "high":
            base_config['format'] = 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]'
            base_config['merge_output_format'] = 'mp4'
        elif quality == "medium":
            base_config['format'] = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]'
            base_config['merge_output_format'] = 'mp4'
        else:  # low
            base_config['format'] = 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]'
            base_config['merge_output_format'] = 'mp4'
    else:  # mp3
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
                if file_age > 3600:  # 1 hora
                    try:
                        file.unlink()
                        print(f"🗑️  Arquivo antigo removido: {file.name}")
                    except:
                        pass
    except Exception as e:
        print(f"⚠️  Erro na limpeza: {e}")

def start_cleanup_thread():
    """Inicia thread de limpeza em background"""
    def cleanup_loop():
        while True:
            time.sleep(3600)  # A cada hora
            cleanup_old_files()
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    print("✅ Thread de limpeza iniciada")

# ==================== ROTAS PRINCIPAIS ====================
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Endpoint de saúde da aplicação"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(video_info_cache),
        'downloads_dir_size': sum(f.stat().st_size for f in DOWNLOADS_DIR.glob('*') if f.is_file())
    })

@app.route('/api/preview', methods=['POST'])
def preview_video():
    """Obtém informações do vídeo"""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({
                'error': 'Muitas requisições. Por favor, aguarde um momento.',
                'retry_after': 60
            }), 429
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON inválidos'}), 400
        
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        # Verificar se é URL do YouTube
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return jsonify({'error': 'URL do YouTube inválida'}), 400
        
        # Verificar cache
        cache_key = f"preview_{hash(url)}"
        if cache_key in video_info_cache:
            cache_data, cache_time = video_info_cache[cache_key]
            if time.time() - cache_time < CACHE_DURATION:
                return jsonify(cache_data)
        
        # Estratégias de extração em ordem de tentativa
        strategies = ['web', 'android', 'ios']
        last_error = None
        
        for strategy in strategies:
            try:
                print(f"🔍 Tentando estratégia: {strategy}")
                
                ydl_config = get_ydl_config(strategy)
                ydl_config['extract_flat'] = True
                
                with yt_dlp.YoutubeDL(ydl_config) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    # Formatar dados do vídeo
                    video_data = {
                        'title': info.get('title', 'Sem título'),
                        'duration': info.get('duration', 0),
                        'duration_str': format_duration(info.get('duration', 0)),
                        'thumbnail': info.get('thumbnail', ''),
                        'channel': info.get('channel', 'Canal desconhecido'),
                        'views': info.get('view_count', 0),
                        'upload_date': info.get('upload_date', ''),
                        'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                        'success': True
                    }
                    
                    # Salvar no cache
                    video_info_cache[cache_key] = (video_data, time.time())
                    
                    return jsonify(video_data)
                    
            except yt_dlp.utils.DownloadError as e:
                last_error = str(e)
                print(f"⚠️  Estratégia {strategy} falhou: {e}")
                time.sleep(random.uniform(1, 3))  # Delay entre tentativas
                continue
            except Exception as e:
                last_error = str(e)
                print(f"⚠️  Erro inesperado: {e}")
                break
        
        return jsonify({
            'error': f'Não foi possível obter informações do vídeo. YouTube pode estar bloqueando requisições.',
            'details': last_error
        }), 500
        
    except Exception as e:
        print(f"❌ Erro geral em /api/preview: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Processa download do vídeo"""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({
                'error': 'Muitas requisições. Por favor, aguarde um momento.',
                'retry_after': 60
            }), 429
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON inválidos'}), 400
        
        url = data.get('url', '').strip()
        format_type = data.get('format', 'mp4')
        quality = data.get('quality', 'medium')
        
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        # Validar formato e qualidade
        if format_type not in ['mp4', 'mp3']:
            return jsonify({'error': 'Formato inválido'}), 400
        
        if quality not in ['high', 'medium', 'low']:
            return jsonify({'error': 'Qualidade inválida'}), 400
        
        print(f"📥 Iniciando download: {url[:50]}... | Formato: {format_type} | Qualidade: {quality}")
        
        # Estratégias em ordem de tentativa
        strategies = ['web', 'android', 'ios']
        download_info = None
        last_error = None
        
        for strategy in strategies:
            try:
                print(f"🔄 Tentando estratégia de download: {strategy}")
                
                ydl_config = get_ydl_config(strategy, format_type, quality)
                ydl_config['progress_hooks'] = [lambda d: print(f"📊 Progresso: {d.get('_percent_str', '0%')}") if d['status'] == 'downloading' else None]
                
                with yt_dlp.YoutubeDL(ydl_config) as ydl:
                    # Extrair informações primeiro
                    info = ydl.extract_info(url, download=False)
                    video_title = clean_filename(info.get('title', 'video'))
                    
                    # Configurar nome do arquivo
                    if format_type == 'mp4':
                        filename = f"{video_title}.mp4"
                    else:
                        filename = f"{video_title}.mp3"
                    
                    filepath = DOWNLOADS_DIR / filename
                    
                    # Verificar se arquivo já existe
                    if filepath.exists():
                        filepath = DOWNLOADS_DIR / f"{video_title}_{int(time.time())}.{format_type}"
                    
                    ydl_config['outtmpl'] = str(filepath.with_suffix(''))
                    
                    # Fazer download
                    print(f"⬇️  Baixando: {video_title}")
                    ydl.download([url])
                    
                    download_info = {
                        'success': True,
                        'filename': filepath.name,
                        'title': info.get('title', 'video'),
                        'filesize': os.path.getsize(filepath) if filepath.exists() else 0,
                        'strategy_used': strategy,
                        'has_cookies': os.path.exists(COOKIES_FILE)
                    }
                    
                    print(f"✅ Download concluído: {filepath.name}")
                    break
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                last_error = error_msg
                
                if 'Sign in to confirm' in error_msg:
                    print(f"🔒 YouTube bloqueou (bot detection) - tentando próxima estratégia")
                elif 'Private video' in error_msg:
                    return jsonify({'error': 'Este vídeo é privado e não pode ser baixado'}), 403
                elif 'Video unavailable' in error_msg:
                    return jsonify({'error': 'Vídeo indisponível ou removido'}), 404
                else:
                    print(f"⚠️  Erro de download: {error_msg}")
                
                time.sleep(random.uniform(2, 5))  # Delay maior entre tentativas
                continue
                
            except Exception as e:
                last_error = str(e)
                print(f"❌ Erro inesperado na estratégia {strategy}: {e}")
                break
        
        if download_info:
            # Iniciar limpeza em background
            threading.Thread(target=cleanup_old_files, daemon=True).start()
            return jsonify(download_info)
        else:
            error_message = "Falha no download. O YouTube pode estar bloqueando requisições deste servidor."
            if last_error:
                error_message += f" Detalhes: {last_error}"
            
            return jsonify({
                'error': error_message,
                'suggestion': 'Tente usar uma conta do YouTube (cookies) ou aguarde alguns minutos'
            }), 500
            
    except Exception as e:
        print(f"❌ Erro geral em /api/download: {e}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Serve o arquivo baixado"""
    try:
        # Segurança: validar nome do arquivo
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Nome de arquivo inválido'}), 400
        
        filepath = DOWNLOADS_DIR / filename
        
        if not filepath.exists():
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        # Configurar headers para download
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
        # Adicionar headers para cache e segurança
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        
        # Limpar arquivo após servir (em background)
        def remove_file_async():
            time.sleep(60)  # Aguardar 1 minuto antes de remover
            try:
                if filepath.exists():
                    filepath.unlink()
                    print(f"🗑️  Arquivo removido após download: {filename}")
            except:
                pass
        
        threading.Thread(target=remove_file_async, daemon=True).start()
        
        return response
        
    except Exception as e:
        print(f"❌ Erro ao servir arquivo {filename}: {e}")
        return jsonify({'error': 'Erro ao servir arquivo'}), 500

@app.route('/api/stats')
def get_stats():
    """Retorna estatísticas da aplicação"""
    try:
        files = list(DOWNLOADS_DIR.glob('*'))
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        return jsonify({
            'total_files': len(files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_entries': len(video_info_cache),
            'rate_limit_active': len(request_times),
            'cookies_available': os.path.exists(COOKIES_FILE),
            'server_time': datetime.now().isoformat(),
            'uptime': int(time.time() - app_start_time)
        })
    except:
        return jsonify({'error': 'Não foi possível obter estatísticas'}), 500

# ==================== MANUTENÇÃO ====================
def periodic_maintenance():
    """Executa manutenção periódica"""
    while True:
        time.sleep(1800)  # A cada 30 minutos
        
        # Limpar cache antigo
        try:
            now = time.time()
            to_remove = []
            for key, (_, cache_time) in video_info_cache.items():
                if now - cache_time > CACHE_DURATION:
                    to_remove.append(key)
            
            for key in to_remove:
                del video_info_cache[key]
            
            if to_remove:
                print(f"🧹 Cache limpo: {len(to_remove)} entradas removidas")
                
        except Exception as e:
            print(f"⚠️  Erro na limpeza do cache: {e}")

# ==================== INICIALIZAÇÃO ====================
if __name__ == '__main__':
    # Registrar tempo de início
    app_start_time = time.time()
    
    # Iniciar threads de manutenção
    start_cleanup_thread()
    maintenance_thread = threading.Thread(target=periodic_maintenance, daemon=True)
    maintenance_thread.start()
    
    # Configurações do servidor
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Iniciando Flux Downloader na porta {port}")
    print(f"📁 Diretório de downloads: {DOWNLOADS_DIR.absolute()}")
    print(f"🍪 Cookies disponíveis: {os.path.exists(COOKIES_FILE)}")
    print(f"🔧 Modo debug: {debug}")
    
    # Executar aplicação
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )