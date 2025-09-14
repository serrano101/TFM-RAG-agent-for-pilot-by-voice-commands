from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# Crear el PDF en inglés con estilo enunciativo
pdf_filename_en = "/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/docs/dataset_procedures/A320_Procedures_English.pdf"
doc = SimpleDocTemplate(pdf_filename_en, pagesize=A4,
                        rightMargin=50, leftMargin=50,
                        topMargin=50, bottomMargin=50)

styles = getSampleStyleSheet()
style_title = ParagraphStyle(
    name="Title",
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=16,
    spaceAfter=10
)
style_subtitle = ParagraphStyle(
    name="Subtitle",
    fontName="Helvetica-Bold",
    fontSize=12,
    leading=14,
    spaceAfter=6,
    spaceBefore=6
)
style_normal = ParagraphStyle(
    name="Normal",
    fontName="Helvetica",
    fontSize=11,
    leading=14,
    spaceAfter=10
)

flow = []

# Normal Procedures
normal_procs = [
    {
        "nombre": "PREFLIGHT PROCEDURE",
        "condiciones": ["Aircraft is on ground and secured before flight."],
        "pasos": [
            "The aircraft documents are checked.",
            "The circuit breakers are confirmed in normal position.",
            "The battery switches are set to ON.",
            "The external power is connected if available.",
            "The ADIRS selectors are set to NAV.",
            "The oxygen pressure is checked."
        ],
        "notas": ["Ensure all required equipment is onboard and serviceable."]
    },
    {
        "nombre": "COCKPIT PREPARATION",
        "condiciones": ["Before engine start."],
        "pasos": [
            "The overhead panel is checked.",
            "The fuel quantity is checked.",
            "The flight plan is entered into the MCDU.",
            "The flight instruments are checked and set.",
            "The takeoff performance data is inserted.",
            "The briefing is completed."
        ],
        "notas": ["All systems must be set according to the flight crew operating manual."]
    },
    {
        "nombre": "ENGINE START",
        "condiciones": ["Aircraft ready for engine start."],
        "pasos": [
            "The beacon light is set to ON.",
            "The parking brake is set.",
            "The engine mode selector is set to IGN/START.",
            "The engine master switch is set to ON for the engine to be started.",
            "Engine parameters are monitored until stabilized."
        ],
        "notas": ["Ground crew is informed before start."]
    },
    {
        "nombre": "BEFORE TAXI",
        "condiciones": ["Engines stabilized and ready to taxi."],
        "pasos": [
            "The ground equipment is cleared.",
            "The flaps are set for takeoff.",
            "The flight controls are checked.",
            "The flight instruments are cross-checked.",
            "The taxi clearance is obtained."
        ],
        "notas": ["Brake check must be performed as soon as aircraft moves."]
    },
    {
        "nombre": "TAXI",
        "condiciones": ["Taxi clearance received."],
        "pasos": [
            "The taxi lights are set ON.",
            "The brakes are checked.",
            "The nose wheel steering is confirmed operative.",
            "The taxi route is followed as cleared."
        ],
        "notas": ["Taxi speed is limited according to airport procedures."]
    },
    {
        "nombre": "BEFORE TAKEOFF",
        "condiciones": ["Lined up or ready for takeoff clearance."],
        "pasos": [
            "The cabin is secured.",
            "The takeoff runway is confirmed.",
            "The TCAS is set to TA/RA.",
            "The packs are set according to requirement.",
            "The flight attendants are advised."
        ],
        "notas": ["Final takeoff checklist is completed."]
    },
    {
        "nombre": "TAKEOFF",
        "condiciones": ["Takeoff clearance received."],
        "pasos": [
            "The thrust levers are set to TOGA or FLEX.",
            "The aircraft is maintained on centerline.",
            "Rotation is performed at VR.",
            "Positive climb is confirmed.",
            "The landing gear is retracted."
        ],
        "notas": ["Monitor engine and flight parameters continuously."]
    },
    {
        "nombre": "AFTER TAKEOFF AND CLIMB",
        "condiciones": ["After initial climb out."],
        "pasos": [
            "The landing gear is retracted.",
            "The flaps and slats are retracted on schedule.",
            "The climb thrust is set.",
            "The autopilot is engaged if desired.",
            "The after takeoff checklist is completed."
        ],
        "notas": ["Transition altitude is observed for setting standard pressure."]
    },
    {
        "nombre": "CRUISE",
        "condiciones": ["Aircraft established at cruise altitude."],
        "pasos": [
            "The cruise power is set.",
            "The fuel monitoring is performed.",
            "The systems are checked regularly.",
            "The position reports are made as required."
        ],
        "notas": ["Maintain situational awareness at all times."]
    },
    {
        "nombre": "DESCENT PREPARATION",
        "condiciones": ["Aircraft approaching top of descent."],
        "pasos": [
            "The descent clearance is obtained.",
            "The STAR and approach are reviewed and inserted.",
            "The landing performance is calculated.",
            "The briefing is completed.",
            "The seat belt signs are set ON."
        ],
        "notas": ["Weather and ATIS information is obtained in advance."]
    },
    {
        "nombre": "APPROACH",
        "condiciones": ["Aircraft established on approach path."],
        "pasos": [
            "The approach mode is armed.",
            "The navigation aids are tuned and identified.",
            "The flaps are extended as required.",
            "The landing gear is extended when cleared.",
            "The landing checklist is completed."
        ],
        "notas": ["Stabilized approach criteria must be met."]
    },
    {
        "nombre": "LANDING",
        "condiciones": ["Aircraft cleared to land."],
        "pasos": [
            "The landing configuration is confirmed.",
            "The autopilot may be disconnected at minimums or earlier.",
            "The aircraft is landed smoothly on main landing gear.",
            "Reversers and brakes are used as required."
        ],
        "notas": ["Landing roll is monitored until safe taxi speed is reached."]
    },
    {
        "nombre": "AFTER LANDING",
        "condiciones": ["Aircraft has vacated the runway."],
        "pasos": [
            "The strobe lights are set OFF.",
            "The landing lights are set OFF.",
            "The APU is started if required.",
            "The flaps are retracted.",
            "The spoilers are disarmed."
        ],
        "notas": ["Ground clearance is obtained before taxiing to stand."]
    },
    {
        "nombre": "PARKING AND SECURING AIRCRAFT",
        "condiciones": ["Aircraft parked at gate or stand."],
        "pasos": [
            "The parking brake is set.",
            "The beacon light is set OFF.",
            "The engines are shut down with ENGINE MASTER set to OFF.",
            "The seat belt signs are set OFF.",
            "The external power is connected if available.",
            "The ADIRS selectors are set to OFF."
        ],
        "notas": ["A full securing checklist is completed before leaving cockpit."]
    }
]
# Lista de procedimientos con frases en inglés
procedimientos_en = [
    {
        "nombre": "ENGINE FIRE ON GROUND",
        "condiciones": ["Fire warning in engine during taxi or rejected takeoff."],
        "pasos": [
            "The ENGINE MASTER of the affected engine is set to OFF.",
            "The ENG FIRE pushbutton of the affected engine is pressed.",
            "The AGENT 1 pushbutton is discharged.",
            "If the fire continues, the AGENT 2 pushbutton is discharged.",
            "Air Traffic Control is informed.",
            "An evacuation is considered."
        ],
        "notas": ["If the fire cannot be extinguished, an immediate evacuation is initiated."]
    },
    {
        "nombre": "ENGINE FIRE IN FLIGHT",
        "condiciones": ["Fire warning in engine during flight."],
        "pasos": [
            "The thrust lever of the affected engine is set to IDLE.",
            "The ENGINE MASTER of the affected engine is set to OFF.",
            "The ENG FIRE pushbutton of the affected engine is pressed.",
            "The AGENT 1 pushbutton is discharged.",
            "If the fire continues, the AGENT 2 pushbutton is discharged.",
            "Speed and altitude are adjusted for a possible immediate landing."
        ],
        "notas": ["Air Traffic Control is contacted for diversion and emergency landing."]
    },
    {
        "nombre": "RAPID DECOMPRESSION",
        "condiciones": ["Sudden loss of cabin pressure."],
        "pasos": [
            "Oxygen masks are set ON with 100% oxygen.",
            "Crew communication is established.",
            "An emergency descent is initiated if required.",
            "The seat belt signs are set to ON.",
            "Cabin crew and passengers are informed."
        ],
        "notas": ["A safe altitude below 10,000 ft is reached as soon as possible."]
    },
    {
        "nombre": "STALL RECOVERY",
        "condiciones": ["Indication of stall or stall warning."],
        "pasos": [
            "Pitch attitude is reduced.",
            "Bank angle is leveled.",
            "Thrust is applied as required.",
            "Speed brakes are retracted.",
            "If in landing configuration, flaps are maintained and landing gear is retracted if necessary."
        ],
        "notas": ["Aerodynamic recovery is prioritized before any other action."]
    },
    {
        "nombre": "UNRELIABLE AIRSPEED",
        "condiciones": ["Inconsistent or unreliable speed indications."],
        "pasos": [
            "The autopilot is set to OFF.",
            "The autothrust is set to OFF.",
            "The flight directors are set to OFF.",
            "Pitch and thrust are adjusted according to reference tables.",
            "If necessary, attitude and power are used as the primary reference."
        ],
        "notas": ["Abrupt maneuvers are avoided until reliable parameters are confirmed."]
    },
    {
        "nombre": "TCAS RA",
        "condiciones": ["Resolution advisory from TCAS."],
        "pasos": [
            "The autopilot is disconnected.",
            "The pitch guidance from TCAS is followed.",
            "No maneuver is made opposite to the RA order.",
            "When clear, the aircraft returns to the original flight path."
        ],
        "notas": ["Immediate compliance is mandatory."]
    },
    {
        "nombre": "GO-AROUND",
        "condiciones": ["Need to abort landing."],
        "pasos": [
            "The thrust levers are set to TOGA.",
            "The flaps are set according to the procedure.",
            "When positive climb is confirmed, the landing gear is retracted.",
            "The flight path is established.",
            "Air Traffic Control is informed."
        ],
        "notas": ["The published missed approach procedure is followed."]
    },
    {
        "nombre": "REJECTED TAKEOFF",
        "condiciones": ["Critical event detected before V1."],
        "pasos": [
            "The thrust levers are set to IDLE.",
            "The reversers are deployed to maximum.",
            "Braking is applied to maximum.",
            "Air Traffic Control is informed.",
            "If required, an evacuation is initiated."
        ],
        "notas": ["Above V1 the takeoff is continued unless the aircraft cannot fly."]
    },
    {
        "nombre": "DITCHING",
        "condiciones": ["Forced landing on water."],
        "pasos": [
            "The ditching pushbutton is pressed.",
            "Cabin crew and passengers are informed.",
            "The approach is configured with landing gear up.",
            "The impact is prepared with the brace position."
        ],
        "notas": ["Air Traffic Control and SAR are contacted if possible."]
    },
    {
        "nombre": "EVACUATION",
        "condiciones": ["Order to evacuate the aircraft."],
        "pasos": [
            "The parking brake is set ON.",
            "The evacuation command is initiated.",
            "Both engine masters are set to OFF.",
            "The APU is set to OFF.",
            "Air Traffic Control is informed."
        ],
        "notas": ["The crew directs passengers to the safe exits."]
    },
    {
        "nombre": "LOSS OF BRAKING",
        "condiciones": ["Loss of braking during landing or taxi."],
        "pasos": [
            "The reversers are set to MAX.",
            "Brake pedals are released.",
            "The anti-skid and nose wheel steering are set to OFF.",
            "Brake pedals are pressed again.",
            "If braking is not restored, the parking brake is applied in short intervals."
        ],
        "notas": ["Prolonged use of the parking brake is avoided to prevent wheel lock."]
    },
    {
        "nombre": "SMOKE OR FUMES",
        "condiciones": ["Detection of smoke or fumes in the cabin or avionics."],
        "pasos": [
            "Oxygen masks are set ON with 100% oxygen.",
            "Crew communication is established.",
            "If necessary, smoke or fumes removal procedures are applied.",
            "Ventilation conditions are adjusted."
        ],
        "notas": ["If smoke persists, an immediate diversion is recommended."]
    },
    {
        "nombre": "FUEL LEAK",
        "condiciones": ["Indications of a fuel leak."],
        "pasos": [
            "The ENGINE MASTER of the affected engine is set to OFF.",
            "The IDG of the affected engine is set to OFF.",
            "Air Traffic Control is informed.",
            "Fuel imbalance is monitored."
        ],
        "notas": ["If safety is compromised, an immediate landing is performed."]
    },
    {
        "nombre": "EMERGENCY DESCENT",
        "condiciones": ["Urgent need to lose altitude rapidly."],
        "pasos": [
            "Oxygen masks are set ON with 100% oxygen.",
            "Crew communication is established.",
            "Speed is set to maximum or appropriate.",
            "Spoilers are set to full.",
            "The selected altitude is confirmed and descent is initiated."
        ],
        "notas": ["Air Traffic Control is informed as soon as possible."]
    },
    {
        "nombre": "EGPWS WARNING (TERRAIN / PULL UP)",
        "condiciones": ["Ground proximity warning from EGPWS."],
        "pasos": [
            "The autopilot is disconnected.",
            "The side stick is pulled fully back.",
            "Thrust is set to TOGA.",
            "Wings are leveled.",
            "Configuration is maintained until clear of terrain."
        ],
        "notas": ["Visual confirmation of terrain is not attempted before maneuvering."]
    },
    {
        "nombre": "WINDSHEAR ESCAPE MANEUVER",
        "condiciones": ["Encounter with windshear."],
        "pasos": [
            "The thrust levers are set to TOGA.",
            "The autopilot is kept ON if appropriate.",
            "The SRS orders are followed.",
            "Configuration is not changed until out of windshear."
        ],
        "notas": ["The priority is to avoid loss of control and maintain a safe climb."]
    }
]

# Emergency/abnormal (reuse from before)
abnormal_procs = procedimientos_en  # from previous code run

# Añadir normales primero
for proc in normal_procs + abnormal_procs:
    flow.append(Paragraph(f"PROCEDURE: {proc['nombre']}", style_title))
    flow.append(Paragraph("CONDITIONS:", style_subtitle))
    for c in proc["condiciones"]:
        flow.append(Paragraph(f"- {c}", style_normal))
    flow.append(Paragraph("STEPS:", style_subtitle))
    for i, p in enumerate(proc["pasos"], start=1):
        flow.append(Paragraph(f"{i}. {p}", style_normal))
    flow.append(Paragraph("NOTES:", style_subtitle))
    for n in proc["notas"]:
        flow.append(Paragraph(f"- {n}", style_normal))
    flow.append(Spacer(1, 12))

# Build final PDF
doc.build(flow)
