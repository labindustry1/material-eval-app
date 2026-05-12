"""3D structural blueprint rendering (lifted from legacy/app_legacy_streamlit.py).

Provides per-topology macro (geometry) and micro (stress/strain heatmap) views
as Plotly figures. Used by the UI to give engineers a visual sense of the
part being evaluated.

This is intentionally a thin demo-grade visualization — for production CAE
results use a proper FEA tool. The micro view's stress patterns are
qualitative (analytical / heuristic shapes), not from real simulation.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go


def render_3d_blueprint(topology: str, dims: dict[str, float], view_type: str = "macro") -> go.Figure:
    """Render a simplified 3D view of a part.

    Args:
        topology: One of BEAM / I_BEAM / PLATE / CORRUGATED / STRAP.
        dims: Geometry dict in mm (length / diameter / width / thickness / height as applicable).
        view_type: "macro" for plain geometry (greyscale), "micro" for qualitative stress heatmap.
    """
    fig = go.Figure()
    title_text = ""

    if topology == "BEAM":
        length = dims.get("length", 300.0)
        diameter = dims.get("diameter", 30.0)
        theta, z = np.meshgrid(np.linspace(0, 2 * np.pi, 30), np.linspace(0, length, 20))
        if view_type == "macro":
            x = (diameter / 2) * np.cos(theta)
            y = (diameter / 2) * np.sin(theta)
            fig.add_trace(go.Surface(x=x, y=y, z=z, colorscale="Greys", opacity=0.9, showscale=False))
            title_text = "📐 宏观几何: 管材/连杆"
        else:
            deflection = 0.1 * diameter * (z / length) ** 2
            x = (diameter / 2) * np.cos(theta) + deflection
            y = (diameter / 2) * np.sin(theta)
            stress_color = length - z
            fig.add_trace(
                go.Surface(
                    x=x, y=y, z=z,
                    surfacecolor=stress_color, colorscale="Inferno",
                    opacity=0.9, showscale=False,
                )
            )
            title_text = "🔥 应力示意: 悬臂受弯，根部应力最大（定性图）"

    elif topology == "I_BEAM":
        length = dims.get("length", 1000.0)
        height = dims.get("height", 100.0)
        width = dims.get("width", 60.0)
        z_arr = np.linspace(0, length, 20)
        if view_type == "macro":
            fig.add_trace(go.Surface(
                x=np.array([[-width / 2, width / 2]] * 20),
                y=np.full((20, 2), height / 2),
                z=np.array([z_arr, z_arr]).T,
                colorscale="Greys", showscale=False,
            ))
            fig.add_trace(go.Surface(
                x=np.array([[-width / 2, width / 2]] * 20),
                y=np.full((20, 2), -height / 2),
                z=np.array([z_arr, z_arr]).T,
                colorscale="Greys", showscale=False,
            ))
            fig.add_trace(go.Surface(
                x=np.zeros((20, 2)),
                y=np.array([[-height / 2, height / 2]] * 20),
                z=np.array([z_arr, z_arr]).T,
                colorscale="Greys", showscale=False,
            ))
            title_text = "📐 宏观几何: 工字梁截面"
        else:
            deflection = 0.05 * length * (z_arr / length) ** 2
            stress_top = np.full((20, 2), 1.0) * (1 - z_arr / length)[:, None]
            stress_bot = np.full((20, 2), 0.8) * (1 - z_arr / length)[:, None]
            stress_web = np.abs(np.array([[-height / 2, height / 2]] * 20)) / (height / 2) * (1 - z_arr / length)[:, None]
            fig.add_trace(go.Surface(
                x=np.array([[-width / 2, width / 2]] * 20) + deflection[:, None],
                y=np.full((20, 2), height / 2),
                z=np.array([z_arr, z_arr]).T,
                surfacecolor=stress_top, colorscale="Jet", showscale=False,
            ))
            fig.add_trace(go.Surface(
                x=np.array([[-width / 2, width / 2]] * 20) + deflection[:, None],
                y=np.full((20, 2), -height / 2),
                z=np.array([z_arr, z_arr]).T,
                surfacecolor=stress_bot, colorscale="Jet", showscale=False,
            ))
            fig.add_trace(go.Surface(
                x=np.zeros((20, 2)) + deflection[:, None],
                y=np.array([[-height / 2, height / 2]] * 20),
                z=np.array([z_arr, z_arr]).T,
                surfacecolor=stress_web, colorscale="Jet", showscale=False,
            ))
            title_text = "🔥 应力示意: 工字梁主轴弯曲（定性图）"

    elif topology == "PLATE":
        length = dims.get("length", 200.0)
        width = dims.get("width", 100.0)
        x_grid, y_grid = np.meshgrid(np.linspace(0, length, 20), np.linspace(0, width, 20))
        if view_type == "macro":
            z_grid = np.zeros_like(x_grid)
            fig.add_trace(go.Surface(
                x=x_grid, y=y_grid, z=z_grid,
                colorscale="Greys", opacity=0.9, showscale=False,
            ))
            title_text = "📐 宏观几何: 平板"
        else:
            z_grid = -0.1 * length * np.sin(x_grid / length * np.pi) * np.sin(y_grid / width * np.pi)
            stress_color = np.abs(z_grid)
            fig.add_trace(go.Surface(
                x=x_grid, y=y_grid, z=z_grid,
                surfacecolor=stress_color, colorscale="Inferno",
                opacity=0.9, showscale=False,
            ))
            title_text = "🔥 应力示意: 中心冲压形变（定性图）"

    elif topology == "CORRUGATED":
        length = dims.get("length", 500.0)
        width = dims.get("width", 300.0)
        thickness = dims.get("thickness", 5.0)
        x_grid, y_grid = np.meshgrid(np.linspace(0, length, 40), np.linspace(0, width, 20))
        if view_type == "macro":
            h_macro = thickness * 3
            x_box = [0, length, length, 0, 0, length, length, 0]
            y_box = [0, 0, width, width, 0, 0, width, width]
            z_box = [-h_macro, -h_macro, -h_macro, -h_macro, h_macro, h_macro, h_macro, h_macro]
            fig.add_trace(go.Mesh3d(
                x=x_box, y=y_box, z=z_box,
                i=[0, 0, 0, 1, 1, 2, 4, 4, 4, 5, 5, 6],
                j=[1, 2, 3, 2, 5, 6, 5, 6, 7, 6, 7, 2],
                k=[2, 3, 0, 5, 6, 1, 6, 7, 4, 7, 2, 7],
                color="lightgrey", opacity=0.4, flatshading=True,
            ))
            title_text = "📐 宏观包络: 波纹板设计空间"
        else:
            z_grid = (thickness * 2) * np.sin(x_grid / length * 10 * np.pi)
            stress_color = np.abs(z_grid)
            fig.add_trace(go.Surface(
                x=x_grid, y=y_grid, z=z_grid,
                surfacecolor=stress_color, colorscale="Jet",
                opacity=0.9, showscale=False,
            ))
            title_text = "🔥 应力示意: 波纹吸能（定性图）"

    elif topology == "STRAP":
        length = dims.get("length", 1000.0)
        width = dims.get("width", 30.0)
        x_grid, y_grid = np.meshgrid(np.linspace(0, length, 20), np.linspace(-width / 2, width / 2, 10))
        if view_type == "macro":
            z_grid = np.zeros_like(x_grid)
            fig.add_trace(go.Surface(
                x=x_grid, y=y_grid, z=z_grid,
                colorscale="Greys", opacity=0.9, showscale=False,
            ))
            title_text = "📐 宏观几何: 柔性织带"
        else:
            necking_factor = 1 - 0.15 * np.sin(x_grid / length * np.pi)
            y_neck = y_grid * necking_factor
            z_grid = np.zeros_like(x_grid)
            stress_color = 1 / necking_factor
            fig.add_trace(go.Surface(
                x=x_grid, y=y_neck, z=z_grid,
                surfacecolor=stress_color, colorscale="Inferno",
                opacity=0.9, showscale=False,
            ))
            title_text = "🔥 应力示意: 拉伸颈缩（定性图）"

    else:
        title_text = f"暂未支持的拓扑：{topology}"

    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=0, r=0, t=30, b=0),
        height=320,
        title=dict(text=title_text, font=dict(color="black", size=14)),
    )
    return fig
