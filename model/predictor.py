#!/usr/bin/env python

import io
from typing import Dict, Optional

import flask

import pandas as pd
import numpy as np
from scipy.stats import distributions as dist

app = flask.Flask(__name__)
DIST_DICT = {
    "center": (3, 3),
    "left": (1, 3),
    "right": (3, 1),
    "uniform": (1, 1),
}

# defining these targets avoids unecessary computation
# (if parameter is given that we do not use, ignore it)
TARGET_COLS = {"dollars_per_hour", "hours_per_shift", "mins_per_plant", "num_plants"}


@app.route("/ping", methods=["GET"])
def ping() -> flask.Response:
    """Determine if the container is working and healthy. In this sample container, we declare
    it healthy if we can load the model successfully."""
    health = Handler.parse_input() is not None  # You can insert a health check here
    status = 200 if health else 404
    return flask.Response(response="\n", status=status, mimetype="application/json")


@app.route("/invocations", methods=["POST"])
def process_request() -> flask.Response:
    """
    Get JSON of input information (metadata) and return an inference.
    """
    data = None

    if flask.request.data is None:
        return flask.Response(
            response="Data is empty", status=420, mimetype="text/plain"
        )
    if flask.request.content_type == "text/json":
        data = flask.request.data.decode("utf-8")
        import ast
        data = ast.literal_eval(data)
    elif flask.request.content_type == "application/json":
        data = flask.request.get_json(force=True)
    else:
        return flask.Response(
            response="This predictor only supports JSON data",
            status=415,
            mimetype="text/plain",
        )

    return handle_request(data)


def handle_request(data: Dict) -> flask.Response:
    """
    Handles the payload dictionary `data`
    """
    keys = data.keys()
    if "config" in keys and "params" in keys:
        dc = data["params"]
        # support for missing names
        names = [f"item {i}" for i in range(20, 0, -1)]
        _config = data["config"]
        _data = {cat["name"] if cat["name"] != "" else names.pop(): cat for cat in dc}
        output_df = inference(_config, _data)
        out = io.StringIO()
        output_df.to_csv(out, header=True, index=False)
        result_str = out.getvalue()
        return flask.Response(response=result_str, status=200, mimetype="text/csv")

    return flask.Response(
        response="Invalid request format. Try again?",
        status=404,
        mimetype="text/plain",
    )


class Handler(object):
    """
    Class to hold invocations model.
    """

    @classmethod
    def parse_input(cls, data: Dict, num_samples: Optional[int] = None) -> pd.DataFrame:
        """For the input, return set of predictions.

        Args:
            data (Dict): The settings for the simulation
            num_samples (int): Simulation fidelity. min = 1E3, max = 1E6

        Returns:
            output_df (pandas.DataFrame): Sampled values

        """
        if num_samples is None:
            num_samples = int(1e4)
        else:
            num_samples = max(int(num_samples), int(1e3))  # prevent too few samples
            num_samples = min(int(num_samples), int(1e6))  # prevent long response time

        input_df = pd.DataFrame(data)
        print("Invoked parser. Inputs:")
        print(input_df)
        output_df = pd.DataFrame()
        column_names = set(input_df.columns) & TARGET_COLS
        for col in column_names:
            column = input_df[col]
            mn, mx = column.loc["min"], column.loc["max"]
            if mn is None:
                mn = 0
            if mx is None:
                mx = 0
            mn, mx = float(mn), float(mx)
            if mn > mx:
                print("min > max, setting param to constant value (min := max).")
                mn = mx

            try:
                dist_type = str(column.loc["uq"])
            except KeyError:
                dist_type = "uniform"
            a, b = DIST_DICT.get(dist_type, (1, 1))
            col_dist = dist.beta(a=a, b=b, loc=mn, scale=mx - mn)
            col_samples = col_dist.rvs(num_samples)
            col_samples = np.round(col_samples, 2)
            output_df[col] = col_samples

        if "dollars_per_hour" in output_df.columns:
            output_df["dollars_per_hour"] = output_df["dollars_per_hour"].round(2)

        integer_types = ["num_plants", "hours_per_shift"]
        for col in set(integer_types) & set(output_df.columns):
            output_df[col] = output_df[col].astype("int")

        # total_col = np.round(total_col, 2)
        # output_df["total"] = total_col
        cls.df = output_df
        # cls.total = output_df["total"].values
        cls.num_samples = num_samples

        return output_df


def filter_and_process_samples(df: pd.DataFrame) -> pd.DataFrame:
    """
    Performs any required clean-up and post-processing.
    """
    df = df.round(2)
    # print(f"\n\tOutput data (head):\n{df.head()}\n")
    print(f"Info:\n{df.describe().T[['min', 'max', 'mean', '50%', 'count']]}")
    output_columns = ["employee_cost_per_day", "num_shifts_per_day"]
    return df[output_columns]


def inference(config: Dict, data: Dict) -> pd.DataFrame:
    """
    Instantiates handler, parses inputs, and cleans up outputs.
    """
    model = Handler()
    df = model.parse_input(data, num_samples=config.get("num_samples", None))
    samples = df.to_dict("list")
    samples = {s: np.array(samples[s]) for s in samples}

    print(f"Inference with {df.shape[1]} supplied parameters")
    cost, shifts = payroll_analysis(**samples)
    df["employee_cost_per_day"] = cost
    df["num_shifts_per_day"] = shifts
    return filter_and_process_samples(df)


def payroll_analysis(
    num_plants=100,
    mins_per_plant=5,
    dollars_per_hour=15,
    hours_per_shift=8,
    **kwds
):
    hours_per_plant_per_day = mins_per_plant / 60.0
    total_hours_per_day = hours_per_plant_per_day * num_plants
    daily_employee_cost = dollars_per_hour * total_hours_per_day
    shifts_per_day = total_hours_per_day / hours_per_shift
    return daily_employee_cost, shifts_per_day
