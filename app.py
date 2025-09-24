import os
import io
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pandas as pd
import plotly.express as px


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


# In-memory store for uploaded dataframes. In production, prefer a persistent cache or object storage.
DATAFRAMES: Dict[str, pd.DataFrame] = {}


def load_csv_to_dataframe(file_storage) -> pd.DataFrame:
	buffer = file_storage.read()
	# Try UTF-8 first, fallback to CP1252
	for encoding in ("utf-8", "cp1252"):
		try:
			return pd.read_csv(io.BytesIO(buffer), encoding=encoding)
		except Exception:
			continue
	# Final attempt: let pandas sniff
	return pd.read_csv(io.BytesIO(buffer))


def clean_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
	if raw_df is None:
		return raw_df
	# Normalize column names
	df = raw_df.copy()
	df.columns = [str(c).strip() for c in df.columns]
	# Drop empty columns (all NaN)
	df = df.dropna(axis=1, how="all")
	# Trim string cells
	for col in df.select_dtypes(include=["object"]).columns:
		df[col] = df[col].astype(str).str.strip()
	# Try to parse dates
	for col in df.columns:
		if df[col].dtype == object:
			try:
				df[col] = pd.to_datetime(df[col], errors="raise")
			except Exception:
				pass
	return df


def infer_column_kinds(df: pd.DataFrame) -> Dict[str, str]:
	"""Return mapping of column -> kind in {numeric, categorical, datetime}."""
	kinds: Dict[str, str] = {}
	for col in df.columns:
		dtype = df[col].dtype
		if pd.api.types.is_numeric_dtype(dtype):
			kinds[col] = "numeric"
		elif pd.api.types.is_datetime64_any_dtype(dtype):
			kinds[col] = "datetime"
		else:
			# Heuristic: few unique values → categorical
			unique_count = df[col].nunique(dropna=True)
			kinds[col] = "categorical" if unique_count <= max(20, int(0.05 * len(df))) else "text"
	return kinds


def suggest_charts(df: pd.DataFrame, kinds: Dict[str, str]) -> List[Tuple[str, str, Optional[str]]]:
	"""
	Return list of (chart_type, x_col, y_col) suggestions ordered by relevance.
	chart_type in {line, bar, pie, scatter, histogram, box}.
	"""
	numeric = [c for c, k in kinds.items() if k == "numeric"]
	cat = [c for c, k in kinds.items() if k == "categorical"]
	dt = [c for c, k in kinds.items() if k == "datetime"]

	suggestions: List[Tuple[str, str, Optional[str]]] = []
	if dt and numeric:
		suggestions.append(("line", dt[0], numeric[0]))
	if cat and numeric:
		suggestions.append(("bar", cat[0], numeric[0]))
	if numeric and len(numeric) >= 2:
		suggestions.append(("scatter", numeric[0], numeric[1]))
	if cat and numeric:
		suggestions.append(("box", cat[0], numeric[0]))
	if numeric:
		suggestions.append(("histogram", numeric[0], None))
	if cat and numeric:
		# Pie needs an aggregate; use first categorical and sum of first numeric
		suggestions.append(("pie", cat[0], numeric[0]))
	return suggestions


def build_figure(
	df: pd.DataFrame,
	chart: str,
	x: Optional[str],
	y: Optional[str],
	color: Optional[str],
	agg: Optional[str],
	title: str,
	color_continuous_scale: Optional[str],
) -> "px.Figure":
	if chart == "line":
		return px.line(df, x=x, y=y, color=color, title=title)
	if chart == "bar":
		return px.bar(df, x=x, y=y, color=color, title=title)
	if chart == "scatter":
		return px.scatter(df, x=x, y=y, color=color, title=title)
	if chart == "histogram":
		return px.histogram(df, x=x or y, color=color, title=title)
	if chart == "box":
		return px.box(df, x=x, y=y, color=color, title=title)
	if chart == "pie":
		if x and y:
			dfg = df.groupby(x, dropna=False)[y].sum().reset_index()
			return px.pie(dfg, names=x, values=y, title=title)
		return px.pie(df, names=x or color, title=title)
	raise ValueError("Unsupported chart type")


@app.route("/", methods=["GET"]) 
def index():
	return render_template("index.html")


@app.route("/upload", methods=["POST"]) 
def upload():
	file = request.files.get("file")
	if not file or file.filename == "":
		flash("Please choose a CSV file to upload.")
		return redirect(url_for("index"))
	try:
		raw_df = load_csv_to_dataframe(file)
		df = clean_dataframe(raw_df)
		upload_id = str(uuid.uuid4())
		DATAFRAMES[upload_id] = df
		return redirect(url_for("configure", upload_id=upload_id))
	except Exception as e:
		flash(f"Failed to read CSV: {e}")
		return redirect(url_for("index"))


@app.route("/configure/<upload_id>", methods=["GET", "POST"]) 
def configure(upload_id: str):
	df = DATAFRAMES.get(upload_id)
	if df is None:
		flash("Upload not found or expired. Please upload again.")
		return redirect(url_for("index"))

	kinds = infer_column_kinds(df)
	suggestions = suggest_charts(df, kinds)
	chart_types = [
		("line", "Line"),
		("bar", "Bar"),
		("pie", "Pie"),
		("scatter", "Scatter"),
		("histogram", "Histogram"),
		("box", "Box"),
	]

	fig_html = None
	selected = {"chart": None, "x": None, "y": None, "color": None, "agg": None, "title": None, "palette": None}

	if request.method == "POST":
		chart = request.form.get("chart")
		x = request.form.get("x") or None
		y = request.form.get("y") or None
		color = request.form.get("color") or None
		agg = request.form.get("agg") or None
		title = request.form.get("title") or ""
		palette = request.form.get("palette") or None
		selected = {"chart": chart, "x": x, "y": y, "color": color, "agg": agg, "title": title, "palette": palette}
		try:
			fig = build_figure(df, chart, x, y, color, agg, title, palette)
			fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
		except Exception as e:
			flash(f"Failed to build chart: {e}")

	return render_template(
		"configure.html",
		upload_id=upload_id,
		columns=list(df.columns),
		kinds=kinds,
		suggestions=suggestions,
		chart_types=chart_types,
		fig_html=fig_html,
		selected=selected,
	)


@app.route("/download/<upload_id>", methods=["POST"]) 
def download_png(upload_id: str):
	df = DATAFRAMES.get(upload_id)
	if df is None:
		flash("Upload not found or expired. Please upload again.")
		return redirect(url_for("index"))
	chart = request.form.get("chart")
	x = request.form.get("x") or None
	y = request.form.get("y") or None
	color = request.form.get("color") or None
	agg = request.form.get("agg") or None
	title = request.form.get("title") or ""
	palette = request.form.get("palette") or None
	fig = build_figure(df, chart, x, y, color, agg, title, palette)
	buf = io.BytesIO()
	fig.write_image(buf, format="png")
	buf.seek(0)
	filename = f"chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
	return send_file(buf, mimetype="image/png", as_attachment=True, download_name=filename)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

