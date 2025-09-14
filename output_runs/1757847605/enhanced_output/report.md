# Enhanced Table of Contents Mapping Report

This report details the enhanced ToC-driven hierarchy repair process with multi-pass mapping,
page-driven parenting, auxiliary content detection, and comprehensive consistency checks.

## 1. Initial Table of Contents from PDF (with Page Intervals)

**Total ToC entries found:** 8

| Level | Title | Start Page | End Page | Interval Size |
|-------|-------|------------|----------|---------------|
| 1 | Sección SI 3 Evacuación de ocupantes | -1 | 3 | 5 |
| 2 | 6 Puertas situadas en recorridos de evacuación | 1 | 1 | 1 |
| 2 | 7 Señalización de los medios de evacuación | 1 | 1 | 1 |
| 2 | 8 Control del humo de incendio | 2 | 2 | 1 |
| 2 | 9 Evacuación de personas con discapacidad en caso de incendio | 3 | 3 | 1 |
| 1 | Sección SI 4 Instalaciones de protección contra incendios | 4 | 1000 | 997 |
| 2 | 1 Dotación de instalaciones de protección contra incendios | 4 | 6 | 3 |
| 2 | 2 Señalización de las instalaciones manuales de protección contra incendios | 7 | 1000 | 994 |

## 2. Multi-Pass Mapping Statistics

**Pass 1 (Exact/Near matches):** 7 matches
**Pass 2 (Structural/Numbered):** 0 matches
**Pass 3 (Fuzzy+Context):** 0 matches
**Pass 4 (Page Scanning):** 0 matches
**Total successful mappings:** 7

## 3. Mapping Quality Analysis

| Pass | ToC Title | Section Header | Similarity | Confidence | Match Type | Page Distance |
|------|-----------|----------------|------------|------------|------------|---------------|
| 1 | 6 Puertas situadas en recorrid | 6 Puertas situadas en recorrid | 1.000 | 1.000 | exact | 0 |
| 1 | 7 Señalización de los medios d | 7 Señalización de los medios d | 1.000 | 1.000 | exact | 0 |
| 1 | 8 Control del humo de incendio | 8 Control del humo de incendio | 1.000 | 1.000 | exact | 0 |
| 1 | 9 Evacuación de personas con d | 9 Evacuación de personas con d | 1.000 | 1.000 | exact | 0 |
| 1 | Sección SI 4 Instalaciones de  | Sección SI 4 Instalaciones de  | 1.000 | 1.000 | exact | 0 |
| 1 | 1 Dotación de instalaciones de | 1 Dotación de instalaciones de | 1.000 | 1.000 | exact | 0 |
| 1 | 2 Señalización de las instalac | 2 Señalización de las instalac | 1.000 | 1.000 | exact | 0 |

## 4. Consistency Check Results

**Level jump violations:** 0
**Page order violations:** 0
**Unique path violations:** 0
**Anejo/Sección cross-contamination:** 0

## 5. Unmapped Content Analysis

### 5.1 PDF ToC Headlines Not Matched (1 entries)

These ToC entries could not be matched to DoclingDocument section headers:

1. **Level 1**: Sección SI 3 Evacuación de ocupantes (Pages -1-3)

## 6. Processing Summary

- **PDF ToC entries processed:** 8
- **DoclingDocument section headers found:** 7
- **Successful ToC mappings:** 7
- **Ground-truth level updates:** 7
- **Derived level updates:** 0
- **Synthetic ToC nodes created:** 0
- **Auxiliary content demoted:** 0
- **Orphaned metadata sections handled:** 0

- **ToC mapping success rate:** 87.5%
- **Section header coverage:** 100.0%

## 7. Final Table of Contents (Ground-Truth + Derived)

Generated from the corrected DoclingDocument with ToC-driven hierarchy:

  - 6 Puertas situadas en recorridos de evacuación
  - 7 Señalización de los medios de evacuación
  - 8 Control del humo de incendio
  - 9 Evacuación de personas con discapacidad en caso de incendio
- Sección SI 4 Instalaciones de protección contra incendios
  - 1 Dotación de instalaciones de protección contra incendios
  - 2 Señalización de las instalaciones manuales de protección contra incendios


---
*Enhanced ToC-driven hierarchy repair completed on 2025-09-14 13:00:26 UTC*
*Multi-pass mapping with page intervals and consistency validation*