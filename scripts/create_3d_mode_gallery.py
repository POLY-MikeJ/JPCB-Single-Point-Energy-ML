"""Generate an offline visual-QA gallery for every supported 3D style."""

from pathlib import Path

import plotly.io as pio

from jpcb_energy.conformer import generate_conformer, plotly_figure


def main() -> None:
    destination=Path(__file__).resolve().parents[1]/"review_artifacts"
    destination.mkdir(parents=True,exist_ok=True)
    molecule,metadata=generate_conformer("CC[N+](C)(C)CCO",42)
    styles=["ball-and-stick","stick","sphere / space-filling","wireframe","cartoon-like","licorice / tube"]
    cards=[]
    for index,style in enumerate(styles):
        figure=plotly_figure(molecule,style=style,color_scheme="element pastel",background="gradient",labels="none",atom_scale=1.0,bond_width=6.0)
        figure.update_layout(height=380,margin={"l":5,"r":5,"t":55,"b":5},title={"text":style.title(),"x":.5,"y":.96,"font":{"size":18,"color":"#0B2B40"}})
        cards.append(f"<section>{pio.to_html(figure,include_plotlyjs=True if index==0 else False,full_html=False,config={'displayModeBar':False})}</section>")
    html=f"""<!doctype html><html><head><meta charset='utf-8'><style>
    body{{margin:0;padding:28px;background:linear-gradient(145deg,#eef8fb,#d7eef4);font:16px Segoe UI,sans-serif;color:#0B2B40}}
    h1{{margin:0 0 6px}}p{{margin:0 0 20px;color:#486581}}main{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}section{{background:white;border:1px solid #cde3eb;border-radius:14px;overflow:hidden;box-shadow:0 5px 18px #0b2b4014}}
    </style></head><body><h1>ZHU MolEnergy · 3D representation validation</h1><p>{metadata['geometry_source']} · illustrative RDKit conformer, not ORCA geometry or a published-paper structure</p><main>{''.join(cards)}</main></body></html>"""
    (destination/"3d_conformer_modes.html").write_text(html,encoding="utf-8")


if __name__=="__main__": main()
