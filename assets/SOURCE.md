# Map boundary source

`ili_states.topojson` was downloaded on 2026-10-15 from:
https://gis.cdc.gov/grasp/fluview/FluView1References/data/State_Territory_FluView1.json

This is the geographic asset used by CDC's public ILI state activity widget. It includes repositioned Alaska, Hawaii, territories, Washington DC, and New York City. `plot_map.py` decodes its TopoJSON arcs and applies a spherical Albers equal-area projection with standard parallels 29.5 and 45.5 degrees, matching the widget's D3 Albers defaults. Inset coordinates are for display, not geographic analysis.

The file is versioned locally so rendering does not require another network request. Activity values and colors are fetched afresh; new jurisdictions without matching geometry fail validation and require a boundary refresh.
