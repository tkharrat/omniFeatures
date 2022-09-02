# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_pressurelines.ipynb.

# %% auto 0
__all__ = ['PressureLines']

# %% ../nbs/01_pressurelines.ipynb 4
import collections
import math
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from fastcore.foundation import L
from sklearn.cluster import KMeans, AgglomerativeClustering, SpectralClustering
from omnisync.visualization.pitch import Pitch,plot_pitch
from operator import itemgetter

# %% ../nbs/01_pressurelines.ipynb 9
class PressureLines:
    def __init__(self, frame, events_to_frame, lineup, clustering_algo, *args, **kwars):
        self.frame, self.lineup, self.events_to_frame = frame, lineup, events_to_frame
        self.algo = clustering_algo(*args, **kwars)
        self.gk_ids = lineup[lineup.position == "GK"].playerId.tolist()
        self.frame_id = frame.name
        self.possession_team_id = events_to_frame.loc[
            events_to_frame.frameId == self.frame_id, "teamId"
        ].values[0]
        self.possession_side = self.lineup.loc[
            self.lineup.teamId == self.possession_team_id, "side"
        ].values[0]
        self.opponent_side = "away" if bool(re.match("home",self.possession_side)) else "home"

    def _prepare_inputs(self):
        "Prepare necessary inputs to pass to the clustering algorithm"
        _player_id_cols = self.frame.filter(like="_player_id").index.tolist()
        linputs = L(
                {
                    "playerId": self.frame[pid_col],
                    "playerStr": pid_col.removesuffix("_player_id"),
                    "jerseyNumber": int(
                        pid_col.removesuffix("_player_id")
                        .removeprefix("away_player_")
                        .removeprefix("home_player_")
                    ),
                    "side": "home" if bool(re.match("home", pid_col)) else "away",
                    "x": self.frame[pid_col.removesuffix("_player_id") + "_x"],
                    "y": self.frame[pid_col.removesuffix("_player_id") + "_y"],
                }
                for pid_col in _player_id_cols
            )
        
        linputs.append( {
                    "playerId": "ball",
                    "playerStr": "ball",
                    "jerseyNumber": 0,
                    "side": "ball",
                    "x": self.frame["ball_x"],
                    "y": self.frame["ball_y"],
                })
        
        self.inputs = pd.DataFrame(linputs).dropna(axis=0)
        self.inputs = self.inputs[~self.inputs.playerId.isin(self.gk_ids)]
        
        self.pl_ids = self.inputs.loc[
                    self.inputs["side"] == self.opponent_side, "playerId"].tolist()

    def _fit(self):
        "Run the clustering algorithm and prepare the output"
        self.xy_input = np.array([
            [x,y] for x , y in zip(
                self.inputs.loc[
                    self.inputs["side"] == self.opponent_side, "x"].tolist(),
                self.inputs.loc[
                    self.inputs['side'] == self.opponent_side, "y"].tolist()
            )
        ])
        
        vp_input = np.array(self.xy_input, copy=True) 
        vp_input[:, 1] =  0
        hp_input = np.array(self.xy_input, copy=True) 
        hp_input[:, 0] =  0
        
        self.vp_output = self.algo.fit_predict(vp_input)
        self.hp_output = self.algo.fit_predict(hp_input)
        
        
    def _sort(self):
        "Sort by cluster nearest the ball"
        def centeroid(coord):
            "calculate centroid of a cluster"
            x, y = zip(coord)
            l = len(x)
            return sum(x)/l, sum(y)/l
        
        def ball_dist(coord,ball=[self.frame["ball_x"],self.frame["ball_y"]]):
            "calculate distance between centroid and ball"
            return math.sqrt(
                (ball[0] - coord[0])**2 + (ball[1] - coord[1])**2 
            )
        
        def sort_one(output, pl_ids=self.pl_ids,coord=self.xy_input):
            "sort dict of player ids"
            clt_dict = collections.defaultdict(list)
            for cluster, _id, coord in zip(output, pl_ids,coord):
                clt_dict[cluster].append([coord,_id])
            
            cntd = dict(
                map(
                    lambda coord: (
                        coord[0],
                        centeroid(coord[1][0][0])),
                    clt_dict.items()
                )
            )
            dist = dict(
                map(
                    lambda coord: (
                        coord[0],
                        ball_dist(
                            coord[1][0][0],
                            [
                                self.frame["ball_x"],self.frame["ball_y"]
                            ]
                        )
                    ), 
                    clt_dict.items()
                )
            )
            
            sort = dict(
                sorted(
                    dist.items(),
                    key=lambda item: item[1]
                )
            )
            
            return [
                list(
                    map(itemgetter(1),
                        clt_dict.get(key))
                ) for key in list(sort.keys())
            ],sort
        
        self.vpl_sorted, self.vpl_keys = sort_one(self.vp_output)
        self.hpl_sorted, self.hpl_keys = sort_one(self.hp_output)
        
        self.pl = pd.DataFrame(
            {
                "frameId": self.frame_id,
                "vPressureline_1": ",".join(press.vpl_sorted[0]),
                "vPressureline_2": ",".join(press.vpl_sorted[1]),
                "vPressureline_3": ",".join(press.vpl_sorted[2]),
                "hPressureline_1": ",".join(press.hpl_sorted[0]),
                "hPressureline_2": ",".join(press.hpl_sorted[1]),
                "hPressureline_3": ",".join(press.hpl_sorted[2]),
                    
            }
            ,index=[0]
        )
    
    def _plot(self,pl="vertical"):
        "Plot the resulting clusters on a football pitch"
        
        pitch = Pitch()
        coord = press.xy_input - [pitch.pitch_size[0] / 2,pitch.pitch_size[1] / 2]
        
        if pl == "vertical":
            plt_vpl = pitch.plot_pitch(show=False)
            plt_vpl.add_trace(
                go.Scatter(
                    x=coord[self.vp_output == list(self.vpl_keys.keys())[0],0],
                    y=coord[self.vp_output == list(self.vpl_keys.keys())[0],1],
                    name="first vertical pressure line"
                )
            )
            plt_vpl.add_trace(
                go.Scatter(
                    x=coord[self.vp_output == list(self.vpl_keys.keys())[1],0],
                    y=coord[self.vp_output == list(self.vpl_keys.keys())[1],1],
                    name="second vertical pressure line"
                )
            )
            plt_vpl.add_trace(
                go.Scatter(
                    x=coord[self.vp_output == list(self.vpl_keys.keys())[2],0],
                    y=coord[self.vp_output == list(self.vpl_keys.keys())[2],1],
                    name="third vertical pressure line"
                )
            )
            plt_vpl.add_trace(
                go.Scatter(
                    x=[self.frame["ball_x"]-pitch.pitch_size[0] / 2], 
                    y=[self.frame["ball_y"]-pitch.pitch_size[1] / 2],
                    name="ball",
                    marker_color="black"
                )
            )
            plt_vpl.update_traces(marker_symbol="circle",marker_size=12)
            
            return plt_vpl            
        
        elif pl == "horizontal":
            plt_hpl = pitch.plot_pitch(show=False)
            plt_hpl.add_trace(
                go.Scatter(
                    x=coord[self.hp_output == list(self.hpl_keys.keys())[0],0],
                    y=coord[self.hp_output == list(self.hpl_keys.keys())[0],1],
                    name="first horizontal pressure line"
                )
            )
            plt_hpl.add_trace(
                go.Scatter(
                    x=coord[self.hp_output == list(self.hpl_keys.keys())[1],0],
                    y=coord[self.hp_output == list(self.hpl_keys.keys())[1],1],
                    name="second horizontal pressure line"
                )
            )
            plt_hpl.add_trace(
                go.Scatter(
                    x=coord[self.hp_output == list(self.hpl_keys.keys())[2],0],
                    y=coord[self.hp_output == list(self.hpl_keys.keys())[2],1],
                    name="third horizontal pressure line"
                )
            )
            plt_hpl.add_trace(
                go.Scatter(
                    x=[self.frame["ball_x"]-pitch.pitch_size[0] / 2], 
                    y=[self.frame["ball_y"]-pitch.pitch_size[1] / 2],
                    name="ball",
                    marker_color="black"
                )
            )
            plt_hpl.update_traces(marker_symbol="circle",marker_size=12)

            return plt_hpl
