//! Native SVG plotting for numeric figures and graphical heatmaps.

use crate::{escape, number, VisualizationError};
use serde::Deserialize;

pub const PROFILE: &str = "reasonscript-plot/0.1";
const MAX_ITEMS: usize = 100_000;
const COLORS: [[u8; 3]; 5] = [
    [68, 1, 84],
    [59, 82, 139],
    [33, 145, 140],
    [94, 201, 98],
    [253, 231, 37],
];

#[derive(Debug, Deserialize)]
pub struct PlotSpec {
    pub schema_version: String,
    #[serde(default = "default_width")]
    pub width: u32,
    #[serde(default = "default_height")]
    pub height: u32,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub x_axis: Axis,
    #[serde(default)]
    pub y_axis: Axis,
    #[serde(default)]
    pub series: Vec<Series>,
    #[serde(default)]
    pub heatmap: Option<Heatmap>,
    #[serde(default)]
    pub shapes: Vec<Shape>,
}

fn default_width() -> u32 {
    960
}
fn default_height() -> u32 {
    540
}

#[derive(Debug, Default, Deserialize)]
pub struct Axis {
    #[serde(default)]
    pub label: String,
    pub min: Option<f64>,
    pub max: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Series {
    Line {
        x: Vec<f64>,
        y: Vec<f64>,
        #[serde(default)]
        label: String,
        #[serde(default)]
        color: Option<String>,
    },
    Scatter {
        x: Vec<f64>,
        y: Vec<f64>,
        #[serde(default)]
        label: String,
        #[serde(default)]
        color: Option<String>,
    },
    Bar {
        x: Vec<f64>,
        y: Vec<f64>,
        #[serde(default)]
        label: String,
        #[serde(default)]
        color: Option<String>,
        #[serde(default = "default_bar_width")]
        width: f64,
    },
}
fn default_bar_width() -> f64 {
    0.8
}

impl Series {
    fn data(&self) -> (&[f64], &[f64], &str, Option<&str>) {
        match self {
            Self::Line { x, y, label, color } | Self::Scatter { x, y, label, color } => {
                (x, y, label, color.as_deref())
            }
            Self::Bar {
                x, y, label, color, ..
            } => (x, y, label, color.as_deref()),
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct Heatmap {
    pub values: Vec<Vec<f64>>,
    #[serde(default)]
    pub x_labels: Vec<String>,
    #[serde(default)]
    pub y_labels: Vec<String>,
    pub min: Option<f64>,
    pub max: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Shape {
    Rectangle {
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        #[serde(default)]
        stroke: Option<String>,
        #[serde(default)]
        fill: Option<String>,
    },
    Circle {
        x: f64,
        y: f64,
        radius: f64,
        #[serde(default)]
        stroke: Option<String>,
        #[serde(default)]
        fill: Option<String>,
    },
    Text {
        x: f64,
        y: f64,
        text: String,
        #[serde(default)]
        color: Option<String>,
    },
}

fn invalid(message: impl Into<String>) -> VisualizationError {
    VisualizationError::new("PLOT-001", message, "plot")
}
fn finite(values: impl IntoIterator<Item = f64>) -> bool {
    values.into_iter().all(f64::is_finite)
}
fn color_valid(color: &str) -> bool {
    color.len() == 7
        && color.starts_with('#')
        && color[1..].bytes().all(|byte| byte.is_ascii_hexdigit())
}
fn check_color(color: Option<&str>) -> Result<(), VisualizationError> {
    if color.is_some_and(|value| !color_valid(value)) {
        Err(invalid("colors must use #RRGGBB"))
    } else {
        Ok(())
    }
}

pub fn validate(spec: &PlotSpec) -> Result<(), VisualizationError> {
    if spec.schema_version != PROFILE {
        return Err(invalid("unsupported plot schema_version"));
    }
    if !(320..=4096).contains(&spec.width) || !(240..=4096).contains(&spec.height) {
        return Err(invalid(
            "figure dimensions must be within 320..4096 by 240..4096",
        ));
    }
    if spec.title.len() > 512 || spec.x_axis.label.len() > 512 || spec.y_axis.label.len() > 512 {
        return Err(invalid("title or axis label is too long"));
    }
    for axis in [&spec.x_axis, &spec.y_axis] {
        if !finite(axis.min.into_iter().chain(axis.max)) {
            return Err(invalid("axis limits must be finite"));
        }
        if matches!((axis.min, axis.max), (Some(min), Some(max)) if min >= max) {
            return Err(invalid("axis minimum must be below maximum"));
        }
    }
    let mut count = spec.shapes.len();
    for series in &spec.series {
        let (x, y, label, color) = series.data();
        if x.is_empty()
            || x.len() != y.len()
            || !finite(x.iter().chain(y).copied())
            || label.len() > 512
        {
            return Err(invalid(
                "series must have matching, finite, nonempty x/y values",
            ));
        }
        check_color(color)?;
        if let Series::Bar { width, .. } = series {
            if !width.is_finite() || *width <= 0.0 {
                return Err(invalid("bar width must be positive and finite"));
            }
        }
        count = count.saturating_add(x.len());
    }
    if let Some(heatmap) = &spec.heatmap {
        let cols = heatmap.values.first().map(Vec::len).unwrap_or(0);
        if cols == 0
            || heatmap
                .values
                .iter()
                .any(|row| row.len() != cols || !finite(row.iter().copied()))
        {
            return Err(invalid(
                "heatmap must be a nonempty rectangular matrix of finite values",
            ));
        }
        if (!heatmap.x_labels.is_empty() && heatmap.x_labels.len() != cols)
            || (!heatmap.y_labels.is_empty() && heatmap.y_labels.len() != heatmap.values.len())
            || heatmap
                .x_labels
                .iter()
                .chain(&heatmap.y_labels)
                .any(|label| label.len() > 512)
        {
            return Err(invalid("heatmap labels must match matrix dimensions"));
        }
        if !finite(heatmap.min.into_iter().chain(heatmap.max))
            || matches!((heatmap.min, heatmap.max), (Some(min), Some(max)) if min >= max || !(max - min).is_finite())
        {
            return Err(invalid("heatmap color limits are invalid"));
        }
        count = count.saturating_add(cols.saturating_mul(heatmap.values.len()));
    }
    for shape in &spec.shapes {
        match shape {
            Shape::Rectangle {
                x,
                y,
                width,
                height,
                stroke,
                fill,
            } => {
                if !finite([*x, *y, *width, *height]) || *width <= 0.0 || *height <= 0.0 {
                    return Err(invalid("rectangle geometry is invalid"));
                }
                check_color(stroke.as_deref())?;
                check_color(fill.as_deref())?;
            }
            Shape::Circle {
                x,
                y,
                radius,
                stroke,
                fill,
            } => {
                if !finite([*x, *y, *radius]) || *radius <= 0.0 {
                    return Err(invalid("circle geometry is invalid"));
                }
                check_color(stroke.as_deref())?;
                check_color(fill.as_deref())?;
            }
            Shape::Text { x, y, text, color } => {
                if !finite([*x, *y]) || text.len() > 512 {
                    return Err(invalid("text annotation is invalid"));
                }
                check_color(color.as_deref())?;
            }
        }
    }
    if count > MAX_ITEMS {
        return Err(VisualizationError::new(
            "PLOT-002",
            "plot exceeds 100000 marks or cells",
            "plot",
        ));
    }
    if spec.series.is_empty() && spec.heatmap.is_none() && spec.shapes.is_empty() {
        return Err(invalid("plot has no marks"));
    }
    Ok(())
}

#[derive(Clone, Copy)]
struct Bounds {
    xmin: f64,
    xmax: f64,
    ymin: f64,
    ymax: f64,
}
impl Bounds {
    fn empty() -> Self {
        Self {
            xmin: f64::INFINITY,
            xmax: f64::NEG_INFINITY,
            ymin: f64::INFINITY,
            ymax: f64::NEG_INFINITY,
        }
    }
    fn include(&mut self, x: f64, y: f64) {
        self.xmin = self.xmin.min(x);
        self.xmax = self.xmax.max(x);
        self.ymin = self.ymin.min(y);
        self.ymax = self.ymax.max(y);
    }
    fn finish(&mut self, spec: &PlotSpec) -> Result<(), VisualizationError> {
        if self.xmin == f64::INFINITY {
            *self = Self {
                xmin: 0.0,
                xmax: 1.0,
                ymin: 0.0,
                ymax: 1.0,
            };
        }
        self.xmin = spec.x_axis.min.unwrap_or(self.xmin);
        self.xmax = spec.x_axis.max.unwrap_or(self.xmax);
        self.ymin = spec.y_axis.min.unwrap_or(self.ymin);
        self.ymax = spec.y_axis.max.unwrap_or(self.ymax);
        if self.xmin == self.xmax {
            self.xmin -= 0.5;
            self.xmax += 0.5;
        }
        if self.ymin == self.ymax {
            self.ymin -= 0.5;
            self.ymax += 0.5;
        }
        if !finite([
            self.xmin,
            self.xmax,
            self.ymin,
            self.ymax,
            self.xmax - self.xmin,
            self.ymax - self.ymin,
        ]) || self.xmin >= self.xmax
            || self.ymin >= self.ymax
        {
            return Err(invalid("plot bounds are not finite and increasing"));
        }
        Ok(())
    }
}

fn bounds(spec: &PlotSpec) -> Result<Bounds, VisualizationError> {
    let mut result = Bounds::empty();
    if let Some(heatmap) = &spec.heatmap {
        result.include(0.0, 0.0);
        result.include(heatmap.values[0].len() as f64, heatmap.values.len() as f64);
    }
    for series in &spec.series {
        let (x, y, _, _) = series.data();
        for (&x, &y) in x.iter().zip(y) {
            result.include(x, y);
        }
        if let Series::Bar { width, .. } = series {
            for &x in x {
                result.include(x - width / 2.0, 0.0);
                result.include(x + width / 2.0, 0.0);
            }
        }
    }
    for shape in &spec.shapes {
        match shape {
            Shape::Rectangle {
                x,
                y,
                width,
                height,
                ..
            } => {
                result.include(*x, *y);
                result.include(x + width, y + height);
            }
            Shape::Circle { x, y, radius, .. } => {
                result.include(x - radius, y - radius);
                result.include(x + radius, y + radius);
            }
            Shape::Text { x, y, .. } => result.include(*x, *y),
        }
    }
    result.finish(spec)?;
    Ok(result)
}

struct Frame {
    left: f64,
    top: f64,
    width: f64,
    height: f64,
    bounds: Bounds,
}
impl Frame {
    fn x(&self, value: f64) -> f64 {
        self.left + (value - self.bounds.xmin) / (self.bounds.xmax - self.bounds.xmin) * self.width
    }
    fn y(&self, value: f64) -> f64 {
        self.top + self.height
            - (value - self.bounds.ymin) / (self.bounds.ymax - self.bounds.ymin) * self.height
    }
}

fn heat_color(value: f64, min: f64, max: f64) -> String {
    let scaled = ((value - min) / (max - min)).clamp(0.0, 1.0) * (COLORS.len() - 1) as f64;
    let low = (scaled as usize).min(COLORS.len() - 2);
    let weight = scaled - low as f64;
    let color = std::array::from_fn::<_, 3, _>(|channel| {
        (COLORS[low][channel] as f64 * (1.0 - weight) + COLORS[low + 1][channel] as f64 * weight)
            .round() as u8
    });
    format!("#{:02x}{:02x}{:02x}", color[0], color[1], color[2])
}

pub fn render_svg(spec: &PlotSpec) -> Result<String, VisualizationError> {
    validate(spec)?;
    let bounds = bounds(spec)?;
    let frame = Frame {
        left: 78.0,
        top: 62.0,
        width: spec.width as f64 - if spec.heatmap.is_some() { 210.0 } else { 120.0 },
        height: spec.height as f64 - 140.0,
        bounds,
    };
    let mut svg = format!("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{}\" height=\"{}\" viewBox=\"0 0 {} {}\">\n", spec.width, spec.height, spec.width, spec.height);
    svg.push_str("<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n");
    svg.push_str(&format!("<text x=\"{}\" y=\"30\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"18\">{}</text>\n", spec.width / 2, escape(&spec.title)));
    for index in 0..=5 {
        let ratio = index as f64 / 5.0;
        let x = frame.left + ratio * frame.width;
        let y = frame.top + (1.0 - ratio) * frame.height;
        svg.push_str(&format!(
            "<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"#e5e7eb\"/>\n",
            number(x),
            number(frame.top),
            number(x),
            number(frame.top + frame.height)
        ));
        svg.push_str(&format!(
            "<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"#e5e7eb\"/>\n",
            number(frame.left),
            number(y),
            number(frame.left + frame.width),
            number(y)
        ));
        if spec
            .heatmap
            .as_ref()
            .map_or(true, |map| map.x_labels.is_empty())
        {
            svg.push_str(&format!("<text x=\"{}\" y=\"{}\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n", number(x), number(frame.top + frame.height + 18.0), number(bounds.xmin + ratio * (bounds.xmax - bounds.xmin))));
        }
        if spec
            .heatmap
            .as_ref()
            .map_or(true, |map| map.y_labels.is_empty())
        {
            svg.push_str(&format!("<text x=\"{}\" y=\"{}\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n", number(frame.left - 9.0), number(y + 4.0), number(bounds.ymin + ratio * (bounds.ymax - bounds.ymin))));
        }
    }
    svg.push_str(&format!(
        "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"#374151\"/>\n",
        number(frame.left),
        number(frame.top),
        number(frame.width),
        number(frame.height)
    ));
    svg.push_str(&format!("<text x=\"{}\" y=\"{}\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"13\">{}</text>\n", number(frame.left + frame.width / 2.0), spec.height - 24, escape(&spec.x_axis.label)));
    svg.push_str(&format!("<text transform=\"translate(20 {}) rotate(-90)\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"13\">{}</text>\n", number(frame.top + frame.height / 2.0), escape(&spec.y_axis.label)));
    if let Some(heatmap) = &spec.heatmap {
        let min = heatmap.min.unwrap_or_else(|| {
            heatmap
                .values
                .iter()
                .flatten()
                .copied()
                .fold(f64::INFINITY, f64::min)
        });
        let max = heatmap.max.unwrap_or_else(|| {
            heatmap
                .values
                .iter()
                .flatten()
                .copied()
                .fold(f64::NEG_INFINITY, f64::max)
        });
        let max = if min == max {
            min + min.abs().max(1.0) * 0.01
        } else {
            max
        };
        if !finite([min, max, max - min]) || min >= max {
            return Err(invalid("heatmap color range is invalid"));
        }
        for (row, values) in heatmap.values.iter().enumerate() {
            for (col, value) in values.iter().enumerate() {
                let x0 = frame.x(col as f64);
                let x1 = frame.x(col as f64 + 1.0);
                let y0 = frame.y(row as f64 + 1.0);
                let y1 = frame.y(row as f64);
                svg.push_str(&format!("<rect class=\"heatmap-cell\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{}\"/>\n", number(x0), number(y0), number(x1 - x0), number(y1 - y0), heat_color(*value, min, max)));
            }
        }
        for (col, label) in heatmap.x_labels.iter().enumerate() {
            svg.push_str(&format!("<text class=\"heatmap-label\" x=\"{}\" y=\"{}\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n", number(frame.x(col as f64 + 0.5)), number(frame.top + frame.height + 34.0), escape(label)));
        }
        for (row, label) in heatmap.y_labels.iter().enumerate() {
            svg.push_str(&format!("<text class=\"heatmap-label\" x=\"{}\" y=\"{}\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n", number(frame.left - 9.0), number(frame.y(row as f64 + 0.5) + 4.0), escape(label)));
        }
        for index in 0..64 {
            let y = frame.top + frame.height * (1.0 - (index + 1) as f64 / 64.0);
            let value = min + (max - min) * index as f64 / 63.0;
            svg.push_str(&format!(
                "<rect x=\"{}\" y=\"{}\" width=\"18\" height=\"{}\" fill=\"{}\"/>\n",
                number(frame.left + frame.width + 34.0),
                number(y),
                number(frame.height / 64.0 + 0.2),
                heat_color(value, min, max)
            ));
        }
        svg.push_str(&format!(
            "<text x=\"{}\" y=\"{}\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n",
            number(frame.left + frame.width + 58.0),
            number(frame.top + 9.0),
            number(max)
        ));
        svg.push_str(&format!(
            "<text x=\"{}\" y=\"{}\" font-family=\"sans-serif\" font-size=\"11\">{}</text>\n",
            number(frame.left + frame.width + 58.0),
            number(frame.top + frame.height),
            number(min)
        ));
    }
    for (series_index, series) in spec.series.iter().enumerate() {
        let (xs, ys, label, color) = series.data();
        let color = color.unwrap_or("#2563eb");
        match series {
            Series::Line { .. } => {
                let points = xs
                    .iter()
                    .zip(ys)
                    .map(|(&x, &y)| format!("{},{}", number(frame.x(x)), number(frame.y(y))))
                    .collect::<Vec<_>>()
                    .join(" ");
                svg.push_str(&format!("<polyline class=\"plot-line\" points=\"{}\" fill=\"none\" stroke=\"{}\" stroke-width=\"2\"/>\n", points, color));
            }
            Series::Scatter { .. } => {
                for (&x, &y) in xs.iter().zip(ys) {
                    svg.push_str(&format!(
                        "<circle class=\"plot-point\" cx=\"{}\" cy=\"{}\" r=\"4\" fill=\"{}\"/>\n",
                        number(frame.x(x)),
                        number(frame.y(y)),
                        color
                    ));
                }
            }
            Series::Bar { width, .. } => {
                for (&x, &y) in xs.iter().zip(ys) {
                    let x0 = frame.x(x - width / 2.0);
                    let x1 = frame.x(x + width / 2.0);
                    let y0 = frame.y(y);
                    let y1 = frame.y(0.0);
                    svg.push_str(&format!("<rect class=\"plot-bar\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{}\"/>\n", number(x0), number(y0.min(y1)), number(x1 - x0), number((y1 - y0).abs()), color));
                }
            }
        }
        if !label.is_empty() {
            svg.push_str(&format!("<text x=\"{}\" y=\"{}\" font-family=\"sans-serif\" font-size=\"12\" fill=\"{}\">● {}</text>\n", number(frame.left + frame.width - 100.0), number(frame.top + 18.0 * series_index as f64 + 18.0), color, escape(label)));
        }
    }
    for shape in &spec.shapes {
        match shape {
            Shape::Rectangle { x, y, width, height, stroke, fill } => svg.push_str(&format!("<rect class=\"plot-shape\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" stroke=\"{}\" fill=\"{}\"/>\n", number(frame.x(*x)), number(frame.y(y + height)), number(frame.x(x + width) - frame.x(*x)), number(frame.y(*y) - frame.y(y + height)), stroke.as_deref().unwrap_or("#111827"), fill.as_deref().unwrap_or("none"))),
            Shape::Circle { x, y, radius, stroke, fill } => svg.push_str(&format!("<ellipse class=\"plot-shape\" cx=\"{}\" cy=\"{}\" rx=\"{}\" ry=\"{}\" stroke=\"{}\" fill=\"{}\"/>\n", number(frame.x(*x)), number(frame.y(*y)), number(frame.x(x + radius) - frame.x(*x)), number(frame.y(*y) - frame.y(y + radius)), stroke.as_deref().unwrap_or("#111827"), fill.as_deref().unwrap_or("none"))),
            Shape::Text { x, y, text, color } => svg.push_str(&format!("<text class=\"plot-shape\" x=\"{}\" y=\"{}\" font-family=\"sans-serif\" font-size=\"13\" fill=\"{}\">{}</text>\n", number(frame.x(*x)), number(frame.y(*y)), color.as_deref().unwrap_or("#111827"), escape(text))),
        }
    }
    svg.push_str("</svg>\n");
    Ok(svg)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_plots_are_deterministic_and_validate_boundaries() {
        let spec: PlotSpec = serde_json::from_value(serde_json::json!({
            "schema_version": PROFILE,
            "series": [{"kind":"line","x":[0,1,2],"y":[0,1,0]}],
            "heatmap": {"values":[[0,1],[2,3]]},
            "shapes": [{"kind":"circle","x":1,"y":1,"radius":0.25}]
        }))
        .unwrap();
        let svg = render_svg(&spec).unwrap();
        assert_eq!(svg, render_svg(&spec).unwrap());
        assert_eq!(svg.matches("class=\"heatmap-cell\"").count(), 4);
        assert!(svg.contains("class=\"plot-line\""));
        assert!(svg.contains("class=\"plot-shape\""));
        let bad: PlotSpec = serde_json::from_value(
            serde_json::json!({"schema_version":PROFILE,"heatmap":{"values":[[1,2],[3]]}}),
        )
        .unwrap();
        assert_eq!(render_svg(&bad).unwrap_err().diagnostic.code, "PLOT-001");
    }
}
