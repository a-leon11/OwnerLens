# Findings report

> The registry analysed here is fictional and was produced by `python -m ownerlens generate`.
> Flags are indicators, not findings of wrongdoing. Each structure has innocent explanations too, and the score only helps decide what to read first.

## Summary

- Companies analysed: **372**
- Companies with at least one flag: **42**
- High risk (score 50+): **12**, medium (25-49): **10**, low: **20**
- Beneficial owner = effective stake of 25% or more, counting every route through other companies

## Flags by rule

| Rule | What it looks for | Points | Companies flagged |
|---|---|---|---|
| R1 | Circular ownership | 30 | 3 |
| R2 | Layered ownership | 25 | 2 |
| R3 | Mass registration address | 20 | 21 |
| R4 | Nominee-style director | 30 | 12 |
| R5 | Stake split to stay under the threshold | 25 | 1 |
| R6 | Ownership that cannot be traced | 30 | 5 |
| R7 | Closed within a year | 20 | 15 |

## Highest-scoring companies (top 20)

| Company | Score | Level | Rules | Beneficial owners | Evidence |
|---|---|---|---|---|---|
| C-0039 Clearwater Hospitality Inc | 70 | high | R3 R4 R7 | P-0165 Quinn Xu 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them<br>dissolved 244 days after it was incorporated |
| C-0145 Hollow Works LLC | 70 | high | R3 R4 R7 | P-0284 Gustavo Delgado 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them<br>dissolved 223 days after it was incorporated |
| C-0244 Juniper Holdings LLC | 70 | high | R3 R4 R7 | P-0113 Irene Patel 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them<br>dissolved 261 days after it was incorporated |
| C-0247 Kingsway Systems LLC | 70 | high | R3 R4 R7 | P-0284 Gustavo Delgado 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them<br>dissolved 192 days after it was incorporated |
| C-0282 Harbor Services Inc | 70 | high | R3 R4 R7 | P-0194 Diego Navarro 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them<br>dissolved 155 days after it was incorporated |
| C-0047 Fjord Capital SA | 50 | high | R3 R4 | P-0165 Quinn Xu 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0052 Cedar Supply Ltd | 50 | high | R3 R4 | P-0113 Irene Patel 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0106 Harbor Partners LLC | 50 | high | R3 R4 | P-0113 Irene Patel 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0116 Unity Capital Ltd | 50 | high | R3 R4 | P-0165 Quinn Xu 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0219 Unity Solutions LLC | 50 | high | R3 R4 | P-0194 Diego Navarro 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0283 Orchard Services Ltd | 50 | high | R3 R4 | P-0284 Gustavo Delgado 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0366 Kingsway Energy Inc | 50 | high | R3 R4 | P-0194 Diego Navarro 100% | 12 companies are registered at 199 Market Road, Stonebridge<br>Quinn Hughes (P-0265) directs 12 companies and owns under 5% of 12 of them |
| C-0044 Lakeshore Solutions SA | 30 | medium | R1 | P-0203 Luis Lopez 55% | part of an ownership loop: C-0044 > C-0140 > C-0133 > C-0044 |
| C-0133 Bluepeak Supply SA | 30 | medium | R1 | P-0172 Felix Patel 55% | part of an ownership loop: C-0044 > C-0140 > C-0133 > C-0044 |
| C-0140 Westbrook Labs Inc | 30 | medium | R1 | P-0287 Nicolas Lopez 55% | part of an ownership loop: C-0044 > C-0140 > C-0133 > C-0044 |
| C-0173 Northbridge Systems Inc | 30 | medium | R6 | none traced | 100% of the ownership cannot be traced to a person |
| C-0206 Fjord Hospitality LLC | 30 | medium | R6 | P-0103 Beatriz Walsh 50% | 50% of the ownership cannot be traced to a person |
| C-0269 Riverbend Partners Inc | 30 | medium | R6 | none traced | 100% of the ownership cannot be traced to a person |
| C-0330 Oakridge Services Inc | 30 | medium | R6 | none traced | 80% of the ownership cannot be traced to a person |
| C-0007 Eastgate Group Inc | 25 | medium | R5 | P-0045 Helena Alvarez 40%; P-0138 Marta Jensen 26%; P-0214 Pablo Walsh 26% | Pablo Walsh (P-0214) holds 26% through 3 routes, none above 16% |

The full list, with every flag, is in `findings.csv`. Flags are indicators, not findings of wrongdoing. Each structure has innocent explanations too, and the score only helps decide what to read first.
