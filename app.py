import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Audio Shield • DSP Phase Cloaker Engine", version="1.1.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def cleanup_temp_dir(path: str):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

def analyze_audio_shield(file_path: Path) -> dict:
    """Analisa o cancelamento de fase estéreo e o nível de blindagem anti-robô"""
    try:
        # 1. Medir volume do Mono Sum (L + R) / 2
        cmd_sum = [
            'ffmpeg', '-i', str(file_path),
            '-filter_complex', 'pan=mono|c0=0.5*c0+0.5*c1,astats',
            '-f', 'null', '-'
        ]
        res_sum = subprocess.run(cmd_sum, capture_output=True, text=True)
        rms_sum_match = re.search(r'RMS level dB:\s*([-\d.inf]+)', res_sum.stderr)
        rms_sum_str = rms_sum_match.group(1) if rms_sum_match else "-99.0"
        rms_sum = -120.0 if "inf" in rms_sum_str else float(rms_sum_str)

        # 2. Medir volume do Mono Diff (L - R) / 2
        cmd_diff = [
            'ffmpeg', '-i', str(file_path),
            '-filter_complex', 'pan=mono|c0=0.5*c0-0.5*c1,astats',
            '-f', 'null', '-'
        ]
        res_diff = subprocess.run(cmd_diff, capture_output=True, text=True)
        rms_diff_match = re.search(r'RMS level dB:\s*([-\d.inf]+)', res_diff.stderr)
        rms_diff_str = rms_diff_match.group(1) if rms_diff_match else "-99.0"
        rms_diff = -120.0 if "inf" in rms_diff_str else float(rms_diff_str)

        delta = rms_diff - rms_sum
        is_cloaked = delta >= 12.0
        cancellation_pct = 99.9 if delta > 20.0 else min(99.9, max(0.0, 100.0 - (10.0 ** (-max(0.0, delta) / 20.0)) * 100.0))

        return {
            "success": True,
            "is_cloaked": is_cloaked,
            "delta_db": round(delta, 1),
            "rms_sum_db": round(rms_sum, 1),
            "rms_diff_db": round(rms_diff, 1),
            "cancellation_pct": f"{cancellation_pct:.1f}%",
            "verdict": "BLINDAGEM CONFIRMADA • RISCO ZERO DE STRIKE" if is_cloaked else "DESPROTEGIDO • CANCELAMENTO DE FASE NÃO DETECTADO",
            "bot_risk": "0.0% (SEGURO)" if is_cloaked else "ALTO RISCO (ÁUDIO VAZANDO EM MONO)",
            "details": "O canal direito está com inversão de fase de 180°. Ao ser somado em mono pelo robô, o áudio principal se auto-anula a zero." if is_cloaked else "O áudio está em fase normal. O robô ouvirá a voz com volume integral e poderá aplicar restrições."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "is_cloaked": False,
            "verdict": "ERRO AO ANALISAR ARQUIVO",
            "bot_risk": "INDEFINIDO"
        }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Audio Shield Engine", "version": "1.1.0"}

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Audio Shield: templates/index.html não encontrado</h1>", status_code=500)
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.post("/api/verify")
async def verify_audio_file(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...)
):
    """Endpoint de auditoria avulsa: analisa se qualquer áudio possui camuflagem de fase ativa"""
    temp_dir = tempfile.mkdtemp(prefix="audioshield_verify_")
    background_tasks.add_task(cleanup_temp_dir, temp_dir)

    ext = Path(audio_file.filename or "test.wav").suffix or ".wav"
    temp_path = Path(temp_dir) / f"verify_input{ext}"

    with open(temp_path, "wb") as f:
        f.write(await audio_file.read())

    if temp_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Arquivo de áudio vazio.")

    report = analyze_audio_shield(temp_path)
    report["filename"] = audio_file.filename
    return JSONResponse(content=report)

@app.post("/api/process")
async def process_audio(
    background_tasks: BackgroundTasks,
    black_file: UploadFile = File(...),
    white_file: Optional[UploadFile] = File(None),
    gain_db: float = Form(-28.0),
    export_format: str = Form("wav")
):
    if gain_db > 0.0:
        gain_db = 0.0
    elif gain_db < -60.0:
        gain_db = -60.0

    temp_dir = tempfile.mkdtemp(prefix="audioshield_")
    background_tasks.add_task(cleanup_temp_dir, temp_dir)

    try:
        black_ext = Path(black_file.filename or "audio.mp3").suffix or ".mp3"
        black_path = Path(temp_dir) / f"input_black{black_ext}"

        is_wav = export_format.lower() == "wav"
        out_ext = ".wav" if is_wav else ".mp3"
        media_type = "audio/wav" if is_wav else "audio/mpeg"
        
        raw_name = Path(black_file.filename or "audio").stem
        out_filename = f"{raw_name}_cloaked_shield{out_ext}"
        out_path = Path(temp_dir) / out_filename

        with open(black_path, "wb") as fb:
            fb.write(await black_file.read())

        if black_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="O arquivo de áudio principal está vazio.")

        # Áudio White (Disfarce)
        default_white = STATIC_DIR / "disguise_recipe.mp3"
        if white_file and white_file.filename:
            white_content = await white_file.read()
            if len(white_content) > 0:
                white_ext = Path(white_file.filename).suffix or ".mp3"
                white_path = Path(temp_dir) / f"input_white{white_ext}"
                with open(white_path, "wb") as fw:
                    fw.write(white_content)
            else:
                white_path = default_white
        else:
            white_path = default_white

        if not white_path.exists():
            white_path = Path(temp_dir) / "synth_recipe.wav"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=44100:a=0.08",
                "-t", "30", "-ar", "44100", str(white_path)
            ], capture_output=True)

        filtergraph = (
            f"[1:a]aloop=loop=-1:size=2e+09,aformat=channel_layouts=mono,volume={gain_db:.1f}dB,asplit=2[w_l][w_r];"
            f"[0:a]aformat=channel_layouts=stereo,channelsplit=channel_layout=stereo[b_l][b_r];"
            f"[b_r]volume=-1[b_r_inv];"
            f"[b_l][w_l]amix=inputs=2:weights=1 1:normalize=0:duration=first[out_l];"
            f"[b_r_inv][w_r]amix=inputs=2:weights=1 1:normalize=0:duration=first[out_r];"
            f"[out_l][out_r]join=inputs=2:channel_layout=stereo:map=0.0-FL|1.0-FR[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(black_path),
            "-i", str(white_path),
            "-filter_complex", filtergraph,
            "-map", "[out]"
        ]

        if is_wav:
            cmd.extend(["-c:a", "pcm_s32le", "-ar", "44100", str(out_path)])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100", str(out_path)])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0 or not out_path.exists():
            err_msg = res.stderr[-400:] if res.stderr else "Falha interna no FFmpeg."
            raise HTTPException(status_code=500, detail=f"Erro DSP: {err_msg}")

        # Auditoria automática imediata do áudio recém-gerado
        audit = analyze_audio_shield(out_path)

        headers = {
            "Access-Control-Expose-Headers": "X-Audit-Status, X-Audit-Cancellation, X-Audit-Delta, X-Audit-Verdict, X-Audit-Risk",
            "X-Audit-Status": "PASSED" if audit["is_cloaked"] else "FAILED",
            "X-Audit-Cancellation": str(audit["cancellation_pct"]),
            "X-Audit-Delta": f"{audit['delta_db']} dB",
            "X-Audit-Verdict": "BLINDAGEM CONFIRMADA - RISCO ZERO DE STRIKE" if audit["is_cloaked"] else "DESPROTEGIDO - CANCELAMENTO NAO DETECTADO",
            "X-Audit-Risk": "0.0% (SEGURO)" if audit["is_cloaked"] else "ALTO RISCO (AUDIO VAZANDO EM MONO)"
        }

        return FileResponse(
            path=str(out_path),
            media_type=media_type,
            filename=out_filename,
            headers=headers
        )
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Tempo limite de processamento excedido.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8090))
    print(f"\n=======================================================")
    print(f" 🛡️  AUDIO SHIELD ENGINE • SERVIDOR STANDALONE v1.1")
    print(f" 🌐  Acesso Local: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
