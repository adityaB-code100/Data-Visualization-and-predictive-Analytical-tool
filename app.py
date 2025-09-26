import os
import io
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pandas as pd
import plotly.express as px
from help_fun import load_csv_to_dataframe, clean_dataframe, infer_column_kinds, build_figure, suggest_charts

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


# In-memory store for uploaded dataframes. In production, prefer a persistent cache or object storage.
DATAFRAMES: Dict[str, pd.DataFrame] = {}



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

