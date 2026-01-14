import os
import yt_dlp
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import time
import subprocess
import random
import datetime
import sys
import json
import tempfile
import glob
import shutil

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui_altere_esta_string_12345'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB

# Criar pasta de downloads se não existir
if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
    os.makedirs(app.config['DOWNLOAD_FOLDER'])

def check_ffmpeg():
    """Verifica se o FFmpeg está instalado"""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      capture_output=True, 
                      check=True)
        return True
    except:
        return False

def get_random_user_agent():
    """Gera um User-Agent aleatório para evitar bloqueios"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    ]
    return random.choice(user_agents)

def get_video_info(url):
    """Obtém informações do vídeo sem fazer download"""
    try:
        # Configuração base
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'user_agent': get_random_user_agent(),
            'referer': 'https://www.youtube.com/',
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Formatar duração
        duration_seconds = info.get('duration', 0)
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        if hours > 0:
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes:02d}:{seconds:02d}"
        
        # Formatar visualizações
        views = info.get('view_count', 0)
        if views >= 1000000:
            views_str = f"{views/1000000:.1f}M"
        elif views >= 1000:
            views_str = f"{views/1000:.1f}K"
        else:
            views_str = str(views)
        
        return {
            'title': info.get('title', 'Sem título'),
            'duration': duration_seconds,
            'duration_str': duration_str,
            'thumbnail': info.get('thumbnail', ''),
            'channel': info.get('uploader', 'Desconhecido'),
            'views': views,
            'views_str': views_str,
            'error': None
        }
    except Exception as e:
        return {'error': str(e)}

@app.route('/', methods=['GET', 'POST'])
def index():
    # Inicializar variáveis com valores padrão
    video_info = None
    url = None
    show_download = False
    has_ffmpeg = check_ffmpeg()
    
    if request.method == 'POST':
        url = request.form.get('url')
        
        if not url:
            flash('Por favor, insira um link do YouTube', 'error')
            return redirect(url_for('index'))
        
        # Verificar se é um link válido do YouTube
        if 'youtube.com' not in url and 'youtu.be' not in url:
            flash('Por favor, insira um link válido do YouTube', 'error')
            return redirect(url_for('index'))
        
        # Obter informações do vídeo
        video_info = get_video_info(url)
        
        if video_info.get('error'):
            flash(f'Erro ao obter informações do vídeo: {video_info["error"]}', 'error')
            return redirect(url_for('index'))
        
        show_download = True
        return render_template('index.html', 
                             video_info=video_info, 
                             url=url,
                             show_download=show_download,
                             has_ffmpeg=has_ffmpeg)
    
    # Para requisições GET
    return render_template('index.html', 
                         video_info=video_info, 
                         url=url,
                         show_download=show_download,
                         has_ffmpeg=has_ffmpeg)

@app.route('/download', methods=['POST'])
def download():
    print("=== INICIANDO DOWNLOAD ===")
    
    try:
        url = request.form.get('url')
        format_choice = request.form.get('format', 'mp4')
        quality = request.form.get('quality', 'medium')
        
        print(f"📥 URL recebida: {url}")
        print(f"🎯 Formato: {format_choice}, Qualidade: {quality}")
        
        if not url:
            flash('URL não fornecida', 'error')
            return redirect(url_for('index'))
        
        # Obter informações do vídeo
        video_info = get_video_info(url)
        if video_info.get('error'):
            flash(f'Erro ao obter informações: {video_info["error"]}', 'error')
            return redirect(url_for('index'))
            
        # Criar nome único com timestamp
        timestamp = int(time.time())
        safe_title = secure_filename(video_info.get('title', 'video'))[:80]
        extension = 'mp3' if format_choice == 'mp3' else 'mp4'
        unique_id = f"{timestamp}_{random.randint(1000, 9999)}"
        
        # Nome base SEM extensão
        base_filename = f"{safe_title}_{unique_id}"
        output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], base_filename)
        
        print(f"🚀 Iniciando download: {url}")
        print(f"📁 Saída: {output_path}")
        
        # Configuração SIMPLIFICADA do yt-dlp
        ydl_opts = {
            'outtmpl': output_path,  # SEM extensão aqui
            'quiet': False,
            'verbose': True,  # Para debug
            'no_warnings': False,
            'user_agent': get_random_user_agent(),
            'referer': 'https://www.youtube.com/',
            'socket_timeout': 60,
            'retries': 10,
            'fragment_retries': 10,
            'ignoreerrors': False,
            'nooverwrites': True,
            'continuedl': True,
            'noplaylist': True,
            'extract_flat': False,
            'concurrent_fragment_downloads': 3,
        }
        
        # Configurar formato
        if format_choice == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'extract_audio': True,
            })
        else:
            # Para vídeo - usar uma única opção confiável
            if quality == 'high' and check_ffmpeg():
                ydl_opts['format'] = 'best[height<=1080]'  # Apenas 1080p
            elif quality == 'medium':
                ydl_opts['format'] = 'best[height<=720]'   # Apenas 720p
            elif quality == 'low':
                ydl_opts['format'] = 'best[height<=480]'   # Apenas 480p
            else:
                ydl_opts['format'] = 'best[ext=mp4]/best'  # Fallback seguro
        
        # SE não tem ffmpeg, forçar formato que não precise de conversão
        if not check_ffmpeg() and format_choice == 'mp4':
            ydl_opts['format'] = 'best[ext=mp4]/best'
            print("⚠️  FFmpeg não encontrado, usando formato MP4 nativo")
        
        # Hook para capturar progresso
        downloaded_file = None
        
        def progress_hook(d):
            nonlocal downloaded_file
            if d['status'] == 'finished':
                downloaded_file = d.get('filename')
                print(f"✅ Download finalizado (hook): {downloaded_file}")
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        try:
            # EXECUTAR DOWNLOAD
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"📥 Baixando: {video_info.get('title', 'desconhecido')}")
                
                # Extrair info primeiro
                info = ydl.extract_info(url, download=False)
                print(f"🎬 Duração: {info.get('duration', 0)}s")
                
                # Download REAL
                print("⏬ Iniciando download via yt-dlp...")
                ydl.download([url])
                print("✅ yt-dlp reportou sucesso")
            
            # Aguardar um pouco para o sistema de arquivos
            time.sleep(2)
            
            # PROCURAR arquivo baixado
            final_file = downloaded_file
            
            # Se o hook não capturou, procurar manualmente
            if not final_file or not os.path.exists(final_file):
                print(f"🔍 Arquivo não encontrado via hook, procurando manualmente...")
                # Padrões de nome possíveis
                possible_patterns = [
                    f"{base_filename}.*",  # Com qualquer extensão
                    f"{safe_title}*{unique_id}*",
                    f"*{unique_id}*"
                ]
                
                for pattern in possible_patterns:
                    matches = glob.glob(os.path.join(app.config['DOWNLOAD_FOLDER'], pattern))
                    if matches:
                        final_file = matches[0]
                        print(f"🔍 Encontrado com padrão {pattern}: {final_file}")
                        break
            
            # Se ainda não encontrou, procurar qualquer arquivo novo (últimos 60 segundos)
            if not final_file or not os.path.exists(final_file):
                print(f"🔍 Procurando arquivos recentes...")
                current_time = time.time()
                for fname in os.listdir(app.config['DOWNLOAD_FOLDER']):
                    fpath = os.path.join(app.config['DOWNLOAD_FOLDER'], fname)
                    if os.path.isfile(fpath):
                        # Arquivo modificado nos últimos 60 segundos
                        if current_time - os.path.getmtime(fpath) < 60:
                            final_file = fpath
                            print(f"🔍 Encontrado arquivo recente: {final_file}")
                            break
            
            # VERIFICAR se encontramos o arquivo
            if final_file and os.path.exists(final_file):
                file_size = os.path.getsize(final_file)
                print(f"📦 Arquivo encontrado: {os.path.basename(final_file)} ({file_size} bytes)")
                
                # Renomear para nome mais limpo (opcional)
                clean_name = f"{safe_title}.{extension}"
                clean_path = os.path.join(app.config['DOWNLOAD_FOLDER'], clean_name)
                
                # Se já existir, adicionar número
                counter = 1
                while os.path.exists(clean_path):
                    clean_name = f"{safe_title}_{counter}.{extension}"
                    clean_path = os.path.join(app.config['DOWNLOAD_FOLDER'], clean_name)
                    counter += 1
                
                try:
                    os.rename(final_file, clean_path)
                    final_file = clean_path
                    clean_name = os.path.basename(final_file)
                    print(f"🔄 Renomeado para: {clean_name}")
                except Exception as e:
                    print(f"⚠️  Não foi possível renomear: {e}")
                    clean_name = os.path.basename(final_file)
                
                # Redirecionar para a página de conclusão
                print(f"🔗 Redirecionando para página de conclusão com arquivo: {clean_name}")
                return redirect(url_for('download_complete', filename=clean_name))
                
            else:
                print("❌ Arquivo não encontrado após download")
                # Listar arquivos na pasta para debug
                print("📁 Conteúdo da pasta de downloads:")
                for f in os.listdir(app.config['DOWNLOAD_FOLDER']):
                    print(f"   - {f}")
                flash('Download concluído, mas o arquivo não foi encontrado. Verifique a pasta "downloads".', 'warning')
                return redirect(url_for('index'))
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            print(f"❌ Erro do yt-dlp: {error_msg}")
            
            if "Unsupported URL" in error_msg:
                flash('URL do YouTube não suportada ou inválida.', 'error')
            elif "Private video" in error_msg:
                flash('Este vídeo é privado ou requer login.', 'error')
            elif "Video unavailable" in error_msg:
                flash('Vídeo não disponível ou foi removido.', 'error')
            elif "ffmpeg" in error_msg.lower():
                flash('FFmpeg necessário. Instale FFmpeg ou escolha qualidade média/baixa.', 'error')
            else:
                flash(f'Erro no download: {error_msg[:150]}', 'error')
            
            return redirect(url_for('index'))
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Erro geral: {error_msg}")
            import traceback
            traceback.print_exc()
            flash(f'Erro inesperado: {error_msg[:100]}', 'error')
            return redirect(url_for('index'))
            
    except Exception as e:
        print(f"❌ Erro na função download: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao processar sua solicitação: {str(e)[:100]}', 'error')
        return redirect(url_for('index'))

@app.route('/download_complete')
def download_complete():
    """Página de conclusão de download"""
    filename = request.args.get('filename', '')
    download_time = datetime.datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    
    # Tentar obter tamanho do arquivo
    file_size = None
    file_exists = False
    if filename:
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            file_exists = True
            size_bytes = os.path.getsize(filepath)
            if size_bytes < 1024 * 1024:  # Menos de 1MB
                file_size = f"{size_bytes / 1024:.1f} KB"
            else:
                file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
    
    return render_template('download_complete.html',
                         filename=filename,
                         download_time=download_time,
                         file_size=file_size,
                         file_exists=file_exists)

@app.route('/download_file/<filename>')
def download_file(filename):
    """Baixa o arquivo diretamente"""
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4' if filename.endswith('.mp4') else 'audio/mpeg' if filename.endswith('.mp3') else 'application/octet-stream'
        )
    else:
        flash('Arquivo não encontrado', 'error')
        return redirect(url_for('index'))

@app.route('/open_download_folder')
def open_download_folder():
    """Abre a pasta de downloads no explorador de arquivos"""
    try:
        folder_path = os.path.abspath(app.config['DOWNLOAD_FOLDER'])
        
        # Diferentes sistemas operacionais
        if os.name == 'nt':  # Windows
            os.startfile(folder_path)
        elif os.name == 'posix':  # Linux/macOS
            import subprocess
            subprocess.call(['open', folder_path] if sys.platform == 'darwin' else ['xdg-open', folder_path])
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cleanup')
def cleanup():
    """Limpa a pasta de downloads"""
    try:
        if os.path.exists(app.config['DOWNLOAD_FOLDER']):
            shutil.rmtree(app.config['DOWNLOAD_FOLDER'])
        os.makedirs(app.config['DOWNLOAD_FOLDER'])
        flash('Pasta de downloads limpa com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao limpar downloads: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/check_ffmpeg')
def check_ffmpeg_route():
    """Rota para verificar status do FFmpeg"""
    has_ffmpeg = check_ffmpeg()
    return {'has_ffmpeg': has_ffmpeg}

@app.route('/help')
def help_page():
    """Página de ajuda"""
    return render_template('help.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/debug_downloads')
def debug_downloads():
    """Página de debug para ver arquivos na pasta de downloads"""
    files = []
    for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        if os.path.isfile(filepath):
            files.append({
                'name': filename,
                'size': os.path.getsize(filepath),
                'modified': time.ctime(os.path.getmtime(filepath)),
                'path': filepath
            })
    
    return jsonify({
        'download_folder': os.path.abspath(app.config['DOWNLOAD_FOLDER']),
        'file_count': len(files),
        'files': files
    })

if __name__ == '__main__':
    print("🔧 Verificando configurações...")
    print(f"📁 Pasta de downloads: {os.path.abspath(app.config['DOWNLOAD_FOLDER'])}")
    
    if not check_ffmpeg():
        print("⚠️  AVISO: FFmpeg não encontrado.")
        print("   Vídeos em alta qualidade podem não funcionar.")
        print("   Para instalar, visite: https://www.gyan.dev/ffmpeg/builds/")
        print("   Ou use apenas as opções 'Média' ou 'Baixa' qualidade.")
    
    print("🚀 Iniciando Flux Downloader...")
    print("🌐 Acesse: http://localhost:5000")
    print("\n📝 LOGS DO DOWNLOAD APARECERÃO AQUI:")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)