import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='Audio Shield • DSP Phase Cloaker Engine', version='1.0.0')

if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

def cleanup_temp_dir(path: str):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

@app.get('/health')
def health_check():
    return {'status': 'ok', 'service': 'Audio Shield Engine', 'version': '1.0.0'}

@app.get('/', response_class=HTMLResponse)
def serve_index():
    index_file = TEMPLATES_DIR / 'index.html'
    if not index_file.exists():
        return HTMLResponse('<h1>Audio Shield: templates/index.html não encontrado</h1>', status_code=500)
    return HTMLResponse(content=index_file.read_text(encoding='utf-8'))

@app.post('/api/process')
async def process_audio(
    background_tasks: BackgroundTasks,
    black_file: UploadFile = File(...),
    white_file: Optional[UploadFile] = File(None),
    gain_db: float = Form(-28.0),
    export_format: str = Form('wav')
):
    if gain_db > 0.0:
        gain_db = 0.0
    elif gain_db < -60.0:
        gain_db = -60.0

    temp_dir = tempfile.mkdtemp(prefix='audioshield_')
    background_tasks.add_task(cleanup_temp_dir, temp_dir)

    try:
        black_ext = Path(black_file.filename or 'audio.mp3').suffix or '.mp3'
        black_path = Path(temp_dir) / f'input_black{black_ext}'

        is_wav = export_format.lower() == 'wav'
        out_ext = '.wav' if is_wav else '.mp3'
        media_type = 'audio/wav' if is_wav else 'audio/mpeg'
        
        raw_name = Path(black_file.filename or 'audio').stem
        out_filename = f'{raw_name}_cloaked_shield{out_ext}'
        out_path = Path(temp_dir) / out_filename

        with open(black_path, 'wb') as fb:
            fb.write(await black_file.read())

        if black_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail='O arquivo de áudio principal está vazio.')

        default_white = STATIC_DIR / 'disguise_recipe.mp3'
        if white_file and white_file.filename:
            white_content = await white_file.read()
            if len(white_content) > 0:
                white_ext = Path(white_file.filename).suffix or '.mp3'
                white_path = Path(temp_dir) / f'input_white{white_ext}'
                with open(white_path, 'wb') as fw:
                    fw.write(white_content)
            else:
                white_path = default_white
        else:
            white_path = default_white

        if not white_path.exists():
            white_path = Path(temp_dir) / 'synth_recipe.wav'
            subprocess.run([
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'anoisesrc=c=pink:r=44100:a=0.08',
                '-t', '30', '-ar', '44100', str(white_path)
            ], capture_output=True)

        filtergraph = (
            f'[1:a]aloop=loop=-1:size=2e+09,aformat=channel_layouts=mono,volume={gain_db:.1f}dB,asplit=2[w_l][w_r];'
            f'[0:a]aformat=channel_layouts=stereo,channelsplit=channel_layout=stereo[b_l][b_r];'
            f'[b_r]volume=-1[b_r_inv];'
            f'[b_l][w_l]amix=inputs=2:weights=1 1:normalize=0:duration=first[out_l];'
            f'[b_r_inv][w_r]amix=inputs=2:weights=1 1:normalize=0:duration=first[out_r];'
            f'[out_l][out_r]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[out]'
        )

        cmd = [
            'ffmpeg', '-y',
            '-i', str(black_path),
            '-i', str(white_path),
            '-filter_complex', filtergraph,
            '-map', '[out]'
        ]

        if is_wav:
            cmd.extend(['-c:a', 'pcm_s32le', '-ar', '44100', str(out_path)])
        else:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '320k', '-ar', '44100', str(out_path)])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0 or not out_path.exists():
            err_msg = res.stderr[-400:] if res.stderr else 'Falha interna no FFmpeg.'
            raise HTTPException(status_code=500, detail=f'Erro DSP: {err_msg}')

        return FileResponse(
            path=str(out_path),
            media_type=media_type,
            filename=out_filename
        )
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail='Tempo limite de processamento excedido.')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro no processamento: {str(e)}')

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8090))
    print(f'\n=======================================================')
    print(f' 🛡️  AUDIO SHIELD ENGINE • SERVIDOR STANDALONE')
    print(f' 🌐  Acesso Local: http://localhost:{port}')
    print(f'=======================================================\n')
    uvicorn.run(app, host='0.0.0.0', port=port)
