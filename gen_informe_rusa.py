from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

doc = Document()

# ── Page setup ──
for section in doc.sections:
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3)
    section.right_margin = Cm(3)

# ── Style config ──
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(12)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.5
style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# Heading styles
for i in range(1, 4):
    heading_style = doc.styles[f'Heading {i}']
    heading_style.font.name = 'Times New Roman'
    heading_style.font.color.rgb = RGBColor(0x1B, 0x2A, 0x4A)
    if i == 1:
        heading_style.font.size = Pt(18)
        heading_style.font.bold = True
        heading_style.paragraph_format.space_before = Pt(24)
        heading_style.paragraph_format.space_after = Pt(12)
    elif i == 2:
        heading_style.font.size = Pt(14)
        heading_style.font.bold = True
        heading_style.paragraph_format.space_before = Pt(18)
        heading_style.paragraph_format.space_after = Pt(8)
    elif i == 3:
        heading_style.font.size = Pt(12)
        heading_style.font.bold = True
        heading_style.paragraph_format.space_before = Pt(12)
        heading_style.paragraph_format.space_after = Pt(6)

def add_para(text, bold=False, italic=False, size=12, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, color=None, space_after=6):
    p = doc.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color
    return p

def add_bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.clear()
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    if level > 0:
        p.paragraph_format.left_indent = Cm(1.27 * (level + 1))
    return p

def set_cell_shading(cell, color):
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shading)

# ═══════════════════════════════════════════════
# TITLE PAGE
# ═══════════════════════════════════════════════
for _ in range(6):
    doc.add_paragraph()

add_para('LA REVOLUCIÓN RUSA (1917)', bold=True, size=26,
         alignment=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x1B, 0x2A, 0x4A), space_after=12)

add_para('Informe Académico — Resumen Ejecutivo', italic=True, size=14,
         alignment=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x55, 0x55, 0x55), space_after=36)

# Horizontal line
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
pPr = p._p.get_or_add_pPr()
pBdr = OxmlElement('w:pBdr')
bottom = OxmlElement('w:bottom')
bottom.set(qn('w:val'), 'single')
bottom.set(qn('w:sz'), '12')
bottom.set(qn('w:space'), '4')
bottom.set(qn('w:color'), '1B2A4A')
pBdr.append(bottom)
pPr.append(pBdr)

add_para('', space_after=12)

add_para('Mayo de 2026', size=12, alignment=WD_ALIGN_PARAGRAPH.CENTER,
         color=RGBColor(0x55, 0x55, 0x55), space_after=6)
add_para('Idioma: Español', size=11, alignment=WD_ALIGN_PARAGRAPH.CENTER,
         color=RGBColor(0x77, 0x77, 0x77))

doc.add_page_break()

# ═══════════════════════════════════════════════
# 1. INTRODUCCIÓN
# ═══════════════════════════════════════════════
doc.add_heading('1. Introducción', level=1)

add_para(
    'La Revolución Rusa de 1917 constituye uno de los acontecimientos más decisivos del siglo XX. '
    'Este proceso revolucionario, desarrollado en dos fases principales —la Revolución de Febrero y la '
    'Revolución de Octubre—, condujo al derrocamiento del régimen monárquico zarista que había gobernado '
    'Rusia durante más de tres siglos y a la instauración del primer Estado socialista de la historia '
    '(Gayubas, 2025). La magnitud de sus consecuencias políticas, económicas y sociales transformó no solo '
    'el destino de la nación rusa, sino el equilibrio geopolítico global durante las décadas siguientes.'
)

add_para(
    'El presente informe ofrece un resumen ejecutivo de los antecedentes, las causas, el desarrollo y las '
    'principales consecuencias de la Revolución Rusa, estructurado con un enfoque académico que integra '
    'fuentes historiográficas actualizadas. Se examinan las condiciones estructurales del Imperio zarista '
    'que propiciaron el estallido revolucionario, las dos etapas del proceso insurreccional y el impacto '
    'duradero que tuvo la revolución en la configuración del mundo contemporáneo.'
)

doc.add_paragraph()

# ═══════════════════════════════════════════════
# 2. ANTECEDENTES Y CAUSAS
# ═══════════════════════════════════════════════
doc.add_heading('2. Antecedentes y Causas', level=1)

doc.add_heading('2.1. El Régimen Zarista', level=2)

add_para(
    'Antes de 1917, el Imperio ruso se regía bajo un sistema autocrático encabezado por la dinastía '
    'Románov desde 1613. El zar Nicolás II (1868-1918), quien accedió al trono en 1894, concentraba '
    'el poder absoluto y gobernaba con el apoyo de una nobleza terrateniente, una burocracia centralizada '
    'y la policía secreta (Ojrana). Rusia era un país esencialmente rural: el 85 % de la población vivía '
    'en el campo y un alto porcentaje de campesinos carecía de tierras, lo que generaba un profundo '
    'malestar social (Wikipedia, 2026).'
)

doc.add_heading('2.2. La Revolución de 1905', level=2)

add_para(
    'Un antecedente directo fue la Revolución de 1905, desencadenada por la derrota rusa en la guerra '
    'ruso-japonesa (1904-1905) y por la sangrienta represión del Domingo Sangriento (22 de enero de 1905), '
    'cuando la Guardia Imperial disparó contra una manifestación pacífica de obreros frente al Palacio de '
    'Invierno, causando cientos de muertos. Las protestas masivas forzaron al zar a crear la Duma Estatal '
    '(asamblea legislativa) y a implementar reformas limitadas; sin embargo, el zar conservó su poder '
    'y restringió el funcionamiento de la Duma, perpetuando el descontento popular (Gayubas, 2025).'
)

doc.add_heading('2.3. La Primera Guerra Mundial como Catalizador', level=2)

add_para(
    'La participación rusa en la Primera Guerra Mundial (1914-1918) agravó todas las contradicciones del '
    'régimen zarista. Las sucesivas derrotas militares —con 1.700.000 muertos y 5.950.000 heridos—, '
    'la ineficiencia de la red ferroviaria y la incapacidad industrial para abastecer al ejército '
    'generaron una crisis económica sin precedentes (Concepto, 2025). La escasez de alimentos provocó '
    'hambrunas en las ciudades, mientras que la inflación erosionaba los salarios obreros. El creciente '
    'descrédito de la familia imperial, acentuado por la influencia del místico Rasputín sobre la '
    'zarina Alejandra (de origen alemán), terminó de minar la legitimidad del régimen.'
)

doc.add_heading('2.4. Causas Estructurales', level=2)

add_para('Las causas principales de la Revolución Rusa pueden sintetizarse en los siguientes factores:')

add_bullet('Desigualdad estructural: opresión y pobreza del campesinado frente a la riqueza concentrada de la nobleza terrateniente.')
add_bullet('Crisis militar: derrotas rusas en la Primera Guerra Mundial y elevadísimo costo humano del conflicto.')
add_bullet('Crisis económica: escasez de alimentos, hambre y desabastecimiento energético, agravados por el duro invierno de 1917.')
add_bullet('Ineficiencia y corrupción del régimen zarista, incapaz de responder a las demandas populares y que recurría sistemáticamente a la represión.')
add_bullet('Crecimiento de la conciencia política: actividad de sindicatos, círculos socialistas, reformistas y revolucionarios desde fines del siglo XIX.')

doc.add_paragraph()

# ════════════════════════════════════
