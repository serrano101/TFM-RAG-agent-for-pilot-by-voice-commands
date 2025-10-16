import os
from TTS.api import TTS
import librosa
import soundfile as sf
import numpy as np
# Elimina imports y shim de transformers y la segunda importación de TTS
# from TTS.api import TTS
# import transformers
# try:
#     import transformers as _tf
#     ...
# except Exception as _e:
#     print(f"[WARN] Transformers shim failed: {_e}")

from TTS.api import TTS

# --- Configuraciones clave de Coqui TTS ---
# Frecuencia para el audio de referencia (los encoders de speaker suelen trabajar a 16k)
TARGET_SR = 16000

def preprocess_and_validate_reference_audio(input_path, output_dir, target_sr=TARGET_SR, max_duration_sec=30):
    """
    Asegura que el audio de referencia esté en el formato adecuado (mono, 22050Hz)
    y lo guarda en un directorio temporal para su uso.

    Args:
        input_path (str): Ruta al archivo de audio de referencia original.
        output_dir (str): Directorio donde guardar el audio preprocesado.
        target_sr (int): Frecuencia de muestreo de destino.
        max_duration_sec (int): Duración máxima permitida en segundos.

    Returns:
        str: La ruta al archivo de audio preprocesado si tiene éxito, None en caso de error.
    """
    os.makedirs(output_dir, exist_ok=True)
    preprocessed_path = os.path.join(output_dir, "reference_audio_preprocessed.wav")
    
    print(f"\n[INFO] Preprocesando audio de referencia: {input_path}")
    
    try:
        # 1. Cargar el audio: Convierte automáticamente a mono si es estéreo, y aplica resample si es necesario.
        # Al cargarlo, limitamos el resampleo solo si la SR es diferente de la TARGET_SR.
        y, sr = librosa.load(input_path, sr=None, mono=True)
        
        # 2. Validación de duración
        duration = librosa.get_duration(y=y, sr=sr)
        if duration > max_duration_sec:
            print(f"[WARNING] Audio demasiado largo ({duration:.2f}s). Se truncará a {max_duration_sec}s.")
            y = y[:int(max_duration_sec * sr)]
        elif duration < 1.0:
            print(f"[ERROR] Audio demasiado corto ({duration:.2f}s). Necesita al menos 1 segundo de voz.")
            return None

        # 3. Resampleo a la SR requerida (solo si es necesario)
        if sr != target_sr:
            print(f"[INFO] Remuestreando de {sr}Hz a {target_sr}Hz...")
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
        else:
            print(f"[INFO] Frecuencia de muestreo correcta: {target_sr}Hz")

        # 4. Normalización simple (opcional, pero ayuda)
        # Normaliza a una amplitud máxima de 0.9 para evitar saturación.
        y = y / np.max(np.abs(y)) * 0.9 

        # 5. Guardar el archivo preprocesado (WAV de 16-bit PCM)
        sf.write(preprocessed_path, y, sr, format='WAV', subtype='PCM_16')
        
        print(f"[SUCCESS] Audio preprocesado guardado en: {preprocessed_path}")
        print(f"[SUCCESS] Nuevo formato: Mono, {sr}Hz, Duración: {librosa.get_duration(y=y, sr=sr):.2f}s")
        return preprocessed_path

    except FileNotFoundError:
        print(f"[FATAL] Archivo de audio no encontrado en la ruta: {input_path}")
        return None
    except Exception as e:
        print(f"[FATAL] Error durante el preprocesamiento del audio: {e}")
        return None
# --- 1. Configuración ---
# El diccionario de datos
DATA = {
    151: "Preflight Procedure",
    152: "Cockpit Preparation",
    153: "Engine Start",
    154: "Before Taxi",
    155: "Taxi",
    156: "Before Takeoff",
    157: "Takeoff",
    158: "After Takeoff and Climb",
    159: "Cruise",
    160: "Descent Preparation",
    161: "Approach",
    162: "Landing",
    163: "After Landing",
    164: "Parking and Securing Aircraft",
    165: "Engine Fire on Ground",
    166: "Engine Fire in Flight",
    167: "Rapid Decompression",
    168: "Stall Recovery",
    169: "Unreliable Airspeed",
    170: "TCAS RA",
    171: "Go-Around",
    172: "Rejected Takeoff",
    173: "Ditching",
    174: "Evacuation",
    175: "Loss of Braking",
    176: "Smoke or Fumes",
    177: "Fuel Leak",
    178: "Emergency Descent",
    179: "EGPWS Warning",
    180: "Windshear Escape Maneuver",
    181: "Preflight Procedure",
    182: "Cockpit Preparation",
    183: "Engine Start",
    184: "Before Taxi",
    185: "Taxi",
    186: "Before Takeoff",
    187: "Takeoff",
    188: "After Takeoff and Climb",
    189: "Cruise",
    190: "Descent Preparation",
    191: "Approach",
    192: "Landing",
    193: "After Landing",
    194: "Parking and Securing Aircraft",
    195: "Engine Fire on Ground",
    196: "Engine Fire in Flight",
    197: "Rapid Decompression",
    198: "Stall Recovery",
    199: "Unreliable Airspeed",
    200: "TCAS RA",
    201: "Stock Market",
    202: "Famous Painters",
    203: "Pet Care",
    204: "Solar System",
    205: "What is the preflight procedure?",
    206: "Describe the cockpit preparation steps.",
    207: "How should an engine start be conducted?",
    208: "What does the before taxi procedure involve?",
    209: "Can you explain the taxi procedure?",
    210: "What is done during the before takeoff procedure?",
    211: "How is a takeoff performed?",
    212: "What are the after takeoff and climb procedures?",
    213: "What are the standard actions during cruise flight?",
    214: "How should the crew prepare for descent?",
    215: "Can you outline the approach procedure?",
    216: "What are the steps for a normal landing?",
    217: "Explain the after landing procedure.",
    218: "How do you correctly park and secure the aircraft?",
    219: "In case of an engine fire on the ground, what is the procedure?",
    220: "What is the procedure if an engine fire occurs in flight?",
    221: "What are the steps to take during a rapid decompression?",
    222: "How do you perform a stall recovery?",
    223: "What is the procedure for unreliable airspeed indications?",
    224: "How should a pilot react to a TCAS RA?",
    225: "What is the procedure for a go-around?",
    226: "When and how is a rejected takeoff performed?",
    227: "What is the procedure for ditching?",
    228: "How is an evacuation of the aircraft carried out?",
    229: "What is the loss of braking procedure?",
    230: "What should be done in case of smoke or fumes in the cockpit?",
    231: "How is a fuel leak handled?",
    232: "Explain the emergency descent procedure.",
    233: "What is the correct response to an EGPWS warning?",
    234: "How is a windshear escape maneuver executed?",
    235: "List the steps for the preflight procedure.",
    236: "Tell me about cockpit preparation.",
    237: "What is the sequence for starting an engine?",
    238: "What checks are part of the 'Before Taxi' procedure?",
    239: "What are the guidelines for taxiing?",
    240: "Describe the 'Before Takeoff' checklist items.",
    241: "What actions are taken during the takeoff roll and initial climb?",
    242: "Can you explain the 'After Takeoff and Climb' procedure?",
    243: "What are the responsibilities during the cruise phase?",
    244: "What is involved in descent preparation?",
    245: "Tell me the procedure for an instrument approach.",
    246: "What happens during the landing phase?",
    247: "What are the pilot's actions after landing?",
    248: "How is the aircraft shut down and secured?",
    249: "What is the fire fighting procedure for an engine on the ground?",
    250: "What is the memory item for an in-flight engine fire?",
    251: "What's the first thing to do in a rapid decompression?",
    252: "How can a pilot recover from a stall?",
    253: "If the speed reading is wrong, what should I do?",
    254: "What is the mandatory action for a TCAS Resolution Advisory?",
    255: "How do you knit a scarf?",
    256: "What are the rules of chess?",
    257: "Can you recommend a good restaurant in Paris?",
    258: "How old are you?",
    259: "How do I get the plane ready from a cold and dark state?",
    260: "What panel should I check before starting the engines?",
    261: "How do I start the second engine after the first one is stabilized?",
    262: "Before calling for pushback, what configuration should the aircraft be in?",
    263: "What's the first check I should perform once the aircraft begins to move?",
    264: "The cabin is ready, we are at the holding point. What are the last items to check?",
    265: "At what point during takeoff do I retract the landing gear?",
    266: "When should I engage the autopilot after becoming airborne?",
    267: "How can I monitor the aircraft's performance while at cruising altitude?",
    268: "Before starting the descent, what information do I need to review and input?",
    269: "When should I extend the landing gear during an approach?",
    270: "What are the primary controls used to land the aircraft smoothly?",
    271: "After vacating, what lights should be turned off?",
    272: "What is the sequence for shutting down the engines when parked at the gate?",
    273: "If the first fire agent bottle doesn't extinguish the fire, what is the next step?",
    274: "What is the priority during a rapid decompression event?",
    275: "In a stall recovery, what is more important: reducing pitch or adding thrust?",
    276: "If my flight instruments are unreliable, what should I use as my primary reference?",
    277: "Should I follow ATC instructions if they contradict a TCAS RA?",
    278: "When performing a go-around, when should the flaps be retracted?",
    279: "At what speed is a takeoff no longer recommended to be rejected?",
    280: "For a water landing, should the landing gear be up or down?",
    281: "What is the first step in ordering an evacuation?",
    282: "If my normal brakes fail, what is the alternative method to slow the aircraft down?",
    283: "If smoke appears, what is the first thing the pilots should do for themselves?",
    284: "Can you write a short poem about the seasons?",
    285: "What is the chemical formula for water?",
    286: "Procedure for",
    287: "Procedure for",
    288: "Explain",
    289: "What is the",
    290: "Procedure for",
    291: "How to play",
    292: "What is the procedure",
    293: "How do you perform",
    294: "What is the response",
    295: "Can you explain",
    296: "What are the steps to follow",
    297: "Who is the current king",
    298: "I have an EGPWS PULL UP warning, but I am in the clouds.",
    299: "After a heavy landing in bad weather, I realize I have no brakes.",
    300: "Provide a detailed analysis"
}

# Nombre del archivo de audio de referencia original
REFERENCE_WAV_PATH_ORIGINAL = "scripts/generated_audio/reference_audio.wav"
PREPROCESSED_AUDIO_DIR = "scripts/generated_audio"
# Directorio donde se guardarán los audios generados
OUTPUT_DIR = "scripts/generated_audio/generated_audios"
# Modelo de Voice Cloning
MODEL_NAME = "tts_models/en/vctk/vits"
DEFAULT_SPEAKER = "p225"  # speaker por defecto para VCTK
# MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
# MODEL_NAME = "tts_models/en/ljspeech/tacotron2-DDC"
# LANGUAGE = "en"


# --- 1. Preprocesamiento y Validación del Audio de Referencia ---
# Desactiva el uso de audio de referencia (ya no se necesita para voz por defecto)
# REFERENCE_WAV_PATH = preprocess_and_validate_reference_audio(
#     input_path=REFERENCE_WAV_PATH_ORIGINAL, 
#     output_dir=PREPROCESSED_AUDIO_DIR
# )
# if REFERENCE_WAV_PATH is None:
#     print("\n[CRITICAL] No se puede continuar sin un audio de referencia válido.")
#     exit()
print("-" * 40)


# --- 2. Inicialización del Modelo ---
print(f"Loading TTS model: {MODEL_NAME}...")

try:
    tts = TTS(model_name=MODEL_NAME)
    print("Model loaded successfully.")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Detectar speakers disponibles y validar DEFAULT_SPEAKER
    available_speakers = getattr(tts, "speakers", None)
    selected_speaker = None
    if available_speakers:
        if DEFAULT_SPEAKER in available_speakers:
            selected_speaker = DEFAULT_SPEAKER
        else:
            selected_speaker = available_speakers[0]
            print(f"[INFO] DEFAULT_SPEAKER '{DEFAULT_SPEAKER}' no disponible. Usando '{selected_speaker}'.")
        print(f"[INFO] Using speaker: {selected_speaker}")
    else:
        print("[INFO] Single-speaker model detected.")

except Exception as e:
    print(f"An error occurred while loading the TTS model: {e}")
    print("Please ensure the 'tts' library is installed, espeak-ng is installed, and you have an internet connection.")
    exit()

# --- 3. Generación de Audios ---
print(f"Starting audio generation for {len(DATA)} entries...")

for audio_id, text_to_speak in DATA.items():
    file_name = f"{audio_id}.wav"
    output_path = os.path.join(OUTPUT_DIR, file_name)
    
    print(f"\nGenerating audio for ID {audio_id}: '{text_to_speak}'...")

    try:
        # Construir kwargs según el tipo de modelo
        kwargs = dict(text=text_to_speak, file_path=output_path)
        if 'available_speakers' in locals() and available_speakers:
            kwargs["speaker"] = selected_speaker

        tts.tts_to_file(**kwargs)
        print(f"   -> Saved to: {output_path}")
    except Exception as e:
        print(f"   -> ERROR generating audio for ID {audio_id}: {e}")
        continue

print("-" * 40)
print("Process completed.")
print(f"Los audios están en: '{OUTPUT_DIR}'")
