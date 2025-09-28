import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dcc
from line_profiler_pycharm import profile
import os
import plotly.io as pio


track_rotations = [('Sakhir', 92.0), ('Jeddah', 104.0), ('Melbourne', 44.0), ('Baku', 357.0), ('Miami', 2.0), ('Monte Carlo', 62.0), ('Catalunya', 95.0), ('Montreal', 62.0), ('Silverstone', 92.0), ('Hungaroring', 40.0), ('Spa-Francorchamps', 91.0), ('Zandvoort', 0.0), ('Monza', 95.0), ('Singapore', 335.0), ('Suzuka', 49.0), ('Lusail', 61.0), ('Austin', 0.0), ('Mexico City', 36.0), ('Interlagos', 0.0), ('Las Vegas', 90.0), ('Yas Marina Circuit', 335.0)]

# Rotation function remains unchanged
def rotate(xy, *, angle):
    rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                        [-np.sin(angle), np.cos(angle)]])
    return np.matmul(xy, rot_mat)


# Convert track plotting to Plotly
def plot_track_map(pos, circuit_info, circuit):
    cache_file = f'cache/{circuit}_twoline_map.json'

    if os.path.exists(cache_file):
        fig = pio.read_json(cache_file)
    else:

        track_rotations = [('Sakhir', 92.0), ('Jeddah', 104.0), ('Melbourne', 44.0), ('Baku', 357.0), ('Miami', 2.0), ('Monte Carlo', 62.0), ('Catalunya', 95.0), ('Montreal', 62.0), ('Silverstone', 92.0), ('Hungaroring', 40.0), ('Spa-Francorchamps', 91.0), ('Zandvoort', 0.0), ('Monza', 95.0), ('Singapore', 335.0), ('Suzuka', 49.0), ('Lusail', 61.0), ('Austin', 0.0), ('Mexico City', 36.0), ('Interlagos', 0.0), ('Las Vegas', 90.0), ('Yas Marina Circuit', 335.0)]
        track = pos[['X', 'Y']].to_numpy()
        track_angle = [rotation for name, rotation in track_rotations if name == circuit][0] / 180 * np.pi
        rotated_track = rotate(track, angle=track_angle)

        # Scale the track by a certain factor
        scale_factor = 1.5  # Adjust as needed
        rotated_track *= scale_factor

        # Calculate the normal vector for each point on the track
        dx = np.gradient(rotated_track[:, 0])
        dy = np.gradient(rotated_track[:, 1])
        normals = np.array([-dy, dx]).T

        # Normalize the normal vectors
        normals /= np.linalg.norm(normals, axis=1)[:, None]

        # Calculate the points for the two sides of the track
        track_width = 600 # Adjust as needed
        track_left = rotated_track + normals
        track_right = rotated_track - normals * track_width

        # Append the first point to the end of the arrays
        rotated_track = np.vstack([rotated_track, rotated_track[0]])
        track_left = np.vstack([track_left, track_left[0]])
        track_right = np.vstack([track_right, track_right[0]])

        fig = go.Figure()

        # Plot the two sides of the track
        fig.add_trace(go.Scatter(x=track_left[:, 0], y=track_left[:, 1], mode='lines', line=dict(color='#636efa', width=0.5)))
        fig.add_trace(go.Scatter(x=track_right[:, 0], y=track_right[:, 1], mode='lines', line=dict(color='#636efa', width=0.5)))

        # Find the x-coordinate of the start-finish line
        start_finish_line_x = [rotated_track[0, 0], rotated_track[0, 0]]

        # Find the y-coordinates of the track boundaries at the x-coordinate of the start-finish line
        track_left_y = np.interp(start_finish_line_x[0], track_left[:, 0], track_left[:, 1])
        track_right_y = np.interp(start_finish_line_x[0], track_right[:, 0], track_right[:, 1])

        # Update the start-finish line to extend only between these y-coordinates
        start_finish_line_y = [track_right_y, track_left_y]

        # Update the start-finish line in the plot
        fig.add_trace(go.Scatter(x=start_finish_line_x, y=start_finish_line_y, mode='lines', line=dict(color='red')))

        # Add corner annotations
        offset_vector = [2500, 0]  # Increase the offset to move the labels further apart

        # Initialize an empty list to store the positions of the annotations
        annotation_positions = []

        # Set the threshold for overlap detection
        threshold = 150  # Adjust this value based on your specific requirements
        # print(circuit_info)
        for _, corner in circuit_info.iterrows():
            # Calculate the initial position of the annotation
            corner_name = str(int(corner['Number'])) if not pd.isna(corner['Number']) else ''
            corner_letter = corner['Letter'] if not pd.isna(corner['Letter']) else ''
            txt = f"{corner_name}{corner_letter}"
            offset_angle = corner['Angle'] / 180 * np.pi
            offset_x, offset_y = rotate(offset_vector, angle=offset_angle)
            text_x = corner['X'] + offset_x
            text_y = corner['Y'] + offset_y
            text_x, text_y = rotate([text_x, text_y], angle=track_angle)

            # Adjust the position of the annotation based on the new scale
            text_x *= scale_factor
            text_y *= scale_factor

            # Check for overlap with existing annotations
            overlap = True
            while overlap:
                overlap = False
                for x, y in annotation_positions:
                    if np.sqrt((x - text_x) ** 2 + (y - text_y) ** 2) < threshold:
                        overlap = True
                        # Adjust the position of the annotation
                        text_x += offset_x
                        text_y += offset_y

            # Add the final position of the annotation to the list
            annotation_positions.append((text_x, text_y))

            # Calculate the position on the outside line of the track
            distances = np.sqrt((track_right[:, 0] - text_x) ** 2 + (track_right[:, 1] - text_y) ** 2)
            closest_point_index = np.argmin(distances)
            outside_x = track_right[closest_point_index, 0]
            outside_y = track_right[closest_point_index, 1]

            # Add annotation for each corner with specified text color
            fig.add_trace(go.Scatter(
                x=[text_x],
                y=[text_y],
                text=[txt],
                mode='text',
                textfont=dict(
                    size=14,
                    color="white"
                ),
                showlegend=False
            ))

            # Add a leader line from the annotation to the corner
            fig.add_trace(go.Scatter(
                x=[outside_x, text_x],
                y=[outside_y, text_y],
                mode='lines',
                line=dict(color='white', width=1),
                showlegend=False
            ))


        # Update layout to hide background, gridlines, and axes
        fig.update_layout(
            showlegend=False,
            plot_bgcolor='#2b2d30',  # Sets the plot area background color
            paper_bgcolor='#2b2d30',  # Transparent background
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                showline=False,  # Hide axis line
                scaleanchor="y",  # Set the x-axis to be anchored to the y-axis
                scaleratio=1,  # Set the aspect ratio of the x-axis to the y-axis
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                showline=False,  # Hide axis line
                scaleanchor="x",  # Set the y-axis to be anchored to the x-axis
                scaleratio=1,  # Set the aspect ratio of the y-axis to the x-axis
                range=[np.min(rotated_track[:, 1]), np.max(rotated_track[:, 1])]
            ),
            autosize=True,
            scene={'aspectmode': 'cube'},
            # width='100%',  # You can adjust the size as needed
            # height='75%',
            margin=dict(l=0, r=0, b=20, t=20, pad=0),
            dragmode=False
        )
        pio.write_json(fig, cache_file)
    return fig


@profile
def interpolate_points(df, threshold):
    new_points = []
    # print('Inconimg date:')
    # print(df['date'])
    # print(df['date'])
    df['date'] = df['date'].astype('int64') / 10 ** 6
    # print(df['date'][0])
    # print(df['date'][1])
    # print(df['date'][2])
    # print(df['date'][3])
    # print(df['date'][4])
    # print(df['date'][5])
    df = df.sort_values('date')

    for i in range(1, len(df)):  # Start from 1 instead of 0
        distance = np.sqrt(
            (df.iloc[i]['x'] - df.iloc[i - 1]['x']) ** 2 + (df.iloc[i]['y'] - df.iloc[i - 1]['y']) ** 2)

        # If the distance exceeds the threshold
        if distance > threshold:
            # Calculate the number of points to interpolate based on the distance
            num_points = int(np.ceil(distance / threshold))

            if i == 0:
                x_values = np.linspace(df.iloc[-1]['x'], df.iloc[0]['x'], num_points)
                y_values = np.linspace(df.iloc[-1]['y'], df.iloc[0]['y'], num_points)
                rpm_values = np.linspace(df.iloc[-1]['rpm'], df.iloc[0]['rpm'], num_points)
                speed_values = np.linspace(df.iloc[-1]['speed'], df.iloc[0]['speed'], num_points)
                n_gear_values = np.linspace(df.iloc[-1]['n_gear'], df.iloc[0]['n_gear'], num_points)
                throttle_values = np.linspace(df.iloc[-1]['throttle'], df.iloc[0]['throttle'], num_points)
                drs_values = np.linspace(df.iloc[-1]['drs'], df.iloc[0]['drs'], num_points)
                brake_values = np.linspace(df.iloc[-1]['brake'], df.iloc[0]['brake'], num_points)
                date_values = np.linspace(df.iloc[-1]['date'], df.iloc[0]['date'], num_points)
            else:
                x_values = np.linspace(df.iloc[i - 1]['x'], df.iloc[i]['x'], num_points)
                y_values = np.linspace(df.iloc[i - 1]['y'], df.iloc[i]['y'], num_points)
                rpm_values = np.linspace(df.iloc[i - 1]['rpm'], df.iloc[i]['rpm'], num_points)
                speed_values = np.linspace(df.iloc[i - 1]['speed'], df.iloc[i]['speed'], num_points)
                n_gear_values = np.linspace(df.iloc[i - 1]['n_gear'], df.iloc[i]['n_gear'], num_points)
                throttle_values = np.linspace(df.iloc[i - 1]['throttle'], df.iloc[i]['throttle'], num_points)
                drs_values = np.linspace(df.iloc[i - 1]['drs'], df.iloc[i]['drs'], num_points)
                brake_values = np.linspace(df.iloc[i - 1]['brake'], df.iloc[i]['brake'], num_points)
                date_values = np.linspace(df.iloc[i - 1]['date'], df.iloc[i]['date'], num_points)

            new_points.extend(list(
                zip(x_values, y_values, rpm_values, speed_values, n_gear_values, throttle_values, drs_values,
                    brake_values, date_values)))

    new_points_df = pd.DataFrame(new_points,
                                 columns=['x', 'y', 'rpm', 'speed', 'n_gear', 'throttle', 'drs', 'brake', 'date'])
    # print("the above line is not the issue")
    # print(new_points_df['date'])
    new_points_df['meeting_key'] = df['meeting_key_x'].iloc[0]
    new_points_df['session_key'] = df['session_key_x'].iloc[0]
    new_points_df['driver_number'] = df['driver_number_x'].iloc[0]
    df = new_points_df

    df['date'] = pd.to_datetime(df['date'], unit='ms')
    # print(df['date'])
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    # print(df['date'])
    # Concatenate the original DataFrame and the new DataFrame
    # df = pd.concat([df, new_points_df], ignore_index=True)

    df['rpm'] = df['rpm'].astype(int)
    df['speed'] = df['speed'].astype(int)
    df['n_gear'] = df['n_gear'].astype(int)
    df['throttle'] = df['throttle'].astype(int)
    df['drs'] = df['drs'].astype(int)
    df['brake'] = df['brake'].astype(int)

    return df


@profile
# Convert track plotting to Plotly
def plot_live_map(pos, circuit_info, circuit,locations_df):
    # print(locations_df.columns)
    # latest_locations_df = locations_df.groupby('driver_number').last().reset_index()
    latest_locations_df = locations_df

    track_rotations = [('Sakhir', 92.0), ('Jeddah', 104.0), ('Melbourne', 44.0), ('Baku', 357.0), ('Miami', 2.0), ('Monte Carlo', 62.0), ('Catalunya', 95.0), ('Montreal', 62.0), ('Silverstone', 92.0), ('Hungaroring', 40.0), ('Spa-Francorchamps', 91.0), ('Zandvoort', 0.0), ('Monza', 95.0), ('Singapore', 335.0), ('Suzuka', 49.0), ('Lusail', 61.0), ('Austin', 0.0), ('Mexico City', 36.0), ('Interlagos', 0.0), ('Las Vegas', 90.0), ('Yas Marina Circuit', 335.0)]
    track = pos[['X', 'Y']].to_numpy()
    track_angle = [rotation for name, rotation in track_rotations if name == circuit][0] / 180 * np.pi
    rotated_track = rotate(track, angle=track_angle)

    # Scale the track by a certain factor
    scale_factor = 1  # Adjust as needed
    rotated_track *= scale_factor

    locations_df[['x', 'y']] = locations_df[['x', 'y']].apply(
        lambda row: pd.Series(rotate([row['x'], row['y']], angle=track_angle) * scale_factor), axis=1)

    fig = go.Figure()

    # Add underlying track map
    # fig.add_trace(
    #     go.Scatter(x=rotated_track[:, 0], y=rotated_track[:, 1], mode='lines', line=dict(color='#636efa', width=12), hoverinfo='skip'))

    # print(len(latest_locations_df))
    # Interpolate the x, y, and speed values to fill in the gaps
    latest_locations_df = interpolate_points(latest_locations_df, 20)
    # print(len(latest_locations_df))

    # Create a new column 'hover_text' that contains the text you want to display on hover
    latest_locations_df['hover_text'] = 'Speed: ' + latest_locations_df['speed'].astype(str) \
                                        + '<br>RPM: ' + latest_locations_df['rpm'].astype(str) \
                                        + '<br>Throttle: ' + latest_locations_df['throttle'].astype(str) \
                                        + '<br>Gear: ' + latest_locations_df['n_gear'].astype(str) \
                                        + '<br>DRS: ' + latest_locations_df['drs'].astype(str) \
                                        + '<br>Brake: ' + latest_locations_df['brake'].astype(str)


    # Plot the interpolated points with a color gradient
    fig.add_trace(go.Scatter(
        x=latest_locations_df['x'],
        y=latest_locations_df['y'],
        mode='markers',
        marker=dict(
            color=latest_locations_df['speed'],
            colorscale='Pinkyl',
            size=7,
            showscale=False,
        ),
        hoverinfo='text',
        text=latest_locations_df['hover_text'],
    ))



    # Add corner annotations
    offset_vector = [1000, 0]  # Increase the offset to move the labels further apart

    # Initialize an empty list to store the positions of the annotations
    annotation_positions = []
    # Set the threshold for overlap detection
    threshold = 500  # Adjust this value based on your specific requirements
    # print(circuit_info)
    for _, corner in circuit_info.iterrows():
        # Calculate the initial position of the annotation
        corner_name = str(int(corner['Number'])) if not pd.isna(corner['Number']) else ''
        corner_letter = corner['Letter'] if not pd.isna(corner['Letter']) else ''
        txt = f"{corner_name}{corner_letter}"
        offset_angle = corner['Angle'] / 180 * np.pi
        offset_x, offset_y = rotate(offset_vector, angle=offset_angle)
        text_x = corner['X'] + offset_x
        text_y = corner['Y'] + offset_y
        text_x, text_y = rotate([text_x, text_y], angle=track_angle)

        # Adjust the position of the annotation based on the new scale
        text_x *= scale_factor
        text_y *= scale_factor

        # Check for overlap with existing annotations
        overlap = True
        while overlap:
            overlap = False
            for x, y in annotation_positions:
                if np.sqrt((x - text_x) ** 2 + (y - text_y) ** 2) < threshold:
                    overlap = True
                    # Adjust the position of the annotation
                    text_x += offset_x
                    text_y += offset_y

        # Add the final position of the annotation to the list
        annotation_positions.append((text_x, text_y))

        # Calculate the position on the track line
        distances = np.sqrt((rotated_track[:, 0] - text_x) ** 2 + (rotated_track[:, 1] - text_y) ** 2)
        closest_point_index = np.argmin(distances)
        outside_x = rotated_track[closest_point_index, 0]
        outside_y = rotated_track[closest_point_index, 1]

        # Add annotation for each corner with specified text color
        fig.add_trace(go.Scatter(
            x=[text_x],
            y=[text_y],
            text=[txt],
            mode='text',
            textfont=dict(
                size=14,
                color="white"
            ),
            showlegend=False,
            hoverinfo='skip'
        ))

        # Add a leader line from the annotation to the corner
        fig.add_trace(go.Scatter(
            x=[outside_x, text_x],
            y=[outside_y, text_y],
            mode='lines',
            line=dict(color='white', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))

    max_y = np.max(rotated_track[:, 1])
    min_y = np.min(rotated_track[:, 1])

    # Update layout to hide background, gridlines, and axes
    fig.update_layout(
        showlegend=False,
        plot_bgcolor='#2b2d30',  # Sets the plot area background color
        paper_bgcolor='#2b2d30',  # Transparent background
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,  # Hide axis line
            scaleanchor="y",  # Set the x-axis to be anchored to the y-axis
            scaleratio=1,  # Set the aspect ratio of the x-axis to the y-axis
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,  # Hide axis line
            scaleanchor="x",  # Set the y-axis to be anchored to the x-axis
            scaleratio=1,  # Set the aspect ratio of the y-axis to the x-axis
            range = [min_y, max_y]
        ),
        autosize=True,
        scene={'aspectmode': 'cube'},
        # width='100%',  # You can adjust the size as needed
        # height='75%',
        margin=dict(l=0, r=0, b=0, t=0, pad=0),
        dragmode=False
    )

    fig.update_yaxes(range=[min_y, max_y])

    # print(len(latest_locations_df))
    # latest_locations_df.to_excel('latest_locations_df.xlsx')
    return fig, latest_locations_df

def plot_telemetry(circuit_info, latest_locations_df, title_font_size=11, axis_title_font_size=11, axis_tick_font_size=11,
                           data_point_size=1, global_margin='0px', plot_height=125):

    locations_df = pd.DataFrame(latest_locations_df)

    # df = car_data_orginal_df
    # print(df.columns)
    # Calculate the differences between each point and the previous point
    locations_df['dx'] = locations_df['x'].diff()
    locations_df['dy'] = locations_df['y'].diff()

    # Calculate the Euclidean distance between each point and the previous point
    locations_df['point_distance'] = np.sqrt(locations_df['dx'] ** 2 + locations_df['dy'] ** 2)

    # Set the distance for the first point to 0
    locations_df.loc[0, 'point_distance'] = 0
    # Calculate the cumulative distance from the start of the track
    locations_df['cumulative_distance'] = locations_df['point_distance'].cumsum()
    # print(locations_df['date'])
    # Drop the temporary columns used for the calculations
    locations_df = locations_df.drop(columns=['dx', 'dy', 'point_distance'])
    # circuit_info['Distance'] = circuit_info['Distance']*10
    locations_df['cumulative_distance'] = locations_df['cumulative_distance']/10
    # print(df['drs'].max())
    circuit_info = circuit_info.rename(columns={'X': 'turn_x', 'Y': 'turn_y'})

    # print(locations_df['cumulative_distance'])
    # print(locations_df['cumulative_distance'].max())
    # print(circuit_info['Distance'])
    # print(circuit_info['Number'].unique())

    # Perform the merge
    locations_df = pd.merge_asof(locations_df, circuit_info, left_on='cumulative_distance', right_on='Distance',
                              direction='nearest')
    # print(locations_df.iloc[0])
    # print(locations_df['Number'])
    unique_turn_numbers = locations_df['Number'].unique()
    # print(unique_turn_numbers)
    # locations_df.to_excel('mapped corners.xlsx')
    # print(locations_df.columns)
    # print(locations_df['Number'].unique())
    # print(locations_df.iloc[0])

    # Define colors for the lines in the order: Plotly's default blue, red, green
    colors = ['#636efa', '#ef553b', '#00cc96']

    # Define plot layout arguments
    def plot_layout_args():
        return {
            'height': plot_height,
            'margin': {'l': 0, 'r': 5, 't': 0, 'b': 55},
            # 'legend': {'orientation': 'h', 'x': 0, 'y': -.5, 'xanchor': 'left', 'yanchor': 'bottom'},
            'dragmode': False,
            'hovermode':'x'
        }

    def create_figure(x, y, name, color, title, yaxis_title):
        locations_df['date'] = pd.to_datetime(locations_df['date'])
        # Group by 'turn_number' and find the median index for each group
        median_indices = locations_df.groupby('Number').apply(lambda x: x.index[int(len(x) / 2)]).values

        # Now use these median indices to select the corresponding dates
        tickvals_dates = locations_df.loc[median_indices, 'date']

        # Convert tickvals_dates to the appropriate format if necessary (e.g., to string if they are datetime objects)
        tickvals = tickvals_dates.dt.strftime('%Y-%m-%dT%H:%M:%S.%f').tolist()

        # Assuming you want the turn numbers as ticktext
        ticktext = locations_df.loc[median_indices, 'Number'].astype(str).tolist()
        fig = go.Figure(data=[
            go.Scatter(x=x, y=y, name=name, mode='lines+markers',
                       marker=dict(size=data_point_size), line=dict(color=color, shape='spline', width=1.5))
        ])
        fig.update_layout(**plot_layout_args(),
            yaxis_title=yaxis_title,
            paper_bgcolor="#2b2d30",  # Sets the background color for the entire figure
            plot_bgcolor="#2b2d30",  # Sets the plot area background color
            font=dict(color="#c9c9c9"),  # Adjusts the font color to improve contrast
            showlegend=False,
            xaxis_zeroline=False,  # Remove the x-axis zero line
            yaxis_zeroline=False,
            xaxis=dict(
                title=dict(
                    text='Turn Number',
                    standoff=10
                ),
                fixedrange=True,
                showgrid=True,  # Ensure gridlines are shown
                gridcolor='#444444',  # Dark grey gridlines
                showspikes=True,
                spikemode='across',
                spikesnap='cursor',
                spikedash='solid',
                spikethickness=2,
                range= [locations_df['date'].min(), locations_df['date'].max()],
                tickmode='array',
                # tickvals=np.arange(1, locations_df['Number'].max()+1, 1),
                tickvals=tickvals,
                # ticktext = [f"{Number}" for Number in np.arange(1, locations_df['Number'].max()+1, 1)],
                ticktext = ticktext,
            ),
            yaxis=dict(
                fixedrange=True,
                showgrid=True,
                gridcolor='#444444',  # Transparent background
            ),
        )

        # fig.update_xaxes(tickformat='%H:%M')
        fig.update_xaxes(showline=False)



        fig.update_xaxes(title_font={'size': axis_title_font_size}, tickfont={'size': axis_tick_font_size})
        fig.update_yaxes(title_font={'size': axis_title_font_size}, tickfont={'size': axis_tick_font_size})
        return fig

    # Create figures
    fig_speed = create_figure(locations_df['date'], locations_df['speed'], 'Speed', colors[0],
                                 'Speed', 'Speed')
    # Add DRS trace to the Speed plot
    fig_speed.add_trace(go.Scatter(x=locations_df['date'], y=locations_df['drs'], name='DRS', mode='lines+markers',
                                   marker=dict(size=data_point_size), line=dict(color=colors[2], shape='spline', width=1.5), yaxis='y2'))
    # Update layout to include the second y-axis for DRS
    fig_speed.update_layout(
        yaxis2=dict(
            title='DRS',
            overlaying='y',
            side='right',
            range=[0, 16],
            showline=False,
            showgrid=False,
            zeroline=False,
            # Set the minimum value to 0 and the maximum value to the maximum value in the DRS data
        )
    )
    fig_rpm = create_figure(locations_df['date'], locations_df['rpm'], 'RPM', colors[1],
                                   'RPM', 'RPM')
    # Add Gear trace to the RPM plot
    fig_rpm.add_trace(go.Scatter(x=locations_df['date'], y=locations_df['n_gear'], name='Gear', mode='lines+markers',
                                   marker=dict(size=data_point_size), line=dict(color=colors[2], shape='spline', width=1.5), yaxis='y2'))
    fig_rpm.update_layout(
        yaxis2=dict(
            title='Gear',
            overlaying='y',
            side='right',
            range=[0, locations_df['n_gear'].max()+2],
            showline=False,
            showgrid=False,
            zeroline=False,
            # Set the minimum value to 0 and the maximum value to the maximum value in the DRS data
        )
    )

    fig_throttle = create_figure(locations_df['date'], locations_df['throttle'], 'Throttle', colors[0], 'Throttle',
                                 'Throttle')
    # Add Brake trace to the Throttle plot
    fig_throttle.add_trace(go.Scatter(x=locations_df['date'], y=locations_df['brake'], name='Brake', mode='lines+markers',
                                      marker=dict(size=data_point_size), line=dict(color=colors[1], shape='spline', width=1.5)))

    return dbc.Container([
        dbc.Row([
            dcc.Graph(id='speed-graph', figure=fig_speed, config={'displayModeBar': False}),  # Speed plot now includes DRS
        ]),
        dbc.Row([
            dcc.Graph(id='rpm-graph', figure=fig_rpm, config={'displayModeBar': False})
        ]),
        dbc.Row([
            dcc.Graph(id='throttle-graph', figure=fig_throttle, config={'displayModeBar': False}),  # Throttle plot now includes Brake
        ])
    ], fluid=True)  # Ensure 'global_margin' is defined or adjust as necessary


def process_drivers_data(drivers_data):
    drivers_df = pd.DataFrame(drivers_data)
    # Convert backup_team_names list to a dictionary for easier access
    backup_team_names_dict = {item['driver_number']: item['team_name'] for item in [
        {'driver_number': 1, 'team_name': 'Red Bull Racing'},
        {'driver_number': 2, 'team_name': 'Williams'},
        {'driver_number': 3, 'team_name': 'RB'},
        {'driver_number': 4, 'team_name': 'McLaren'},
        {'driver_number': 10, 'team_name': 'Alpine'},
        {'driver_number': 11, 'team_name': 'Red Bull Racing'},
        {'driver_number': 14, 'team_name': 'Aston Martin'},
        {'driver_number': 16, 'team_name': 'Ferrari'},
        {'driver_number': 18, 'team_name': 'Aston Martin'},
        {'driver_number': 20, 'team_name': 'Haas F1 Team'},
        {'driver_number': 22, 'team_name': 'RB'},
        {'driver_number': 23, 'team_name': 'Williams'},
        {'driver_number': 24, 'team_name': 'Kick Sauber'},
        {'driver_number': 27, 'team_name': 'Haas F1 Team'},
        {'driver_number': 31, 'team_name': 'Alpine'},
        {'driver_number': 44, 'team_name': 'Mercedes'},
        {'driver_number': 55, 'team_name': 'Ferrari'},
        {'driver_number': 63, 'team_name': 'Mercedes'},
        {'driver_number': 77, 'team_name': 'Kick Sauber'},
        {'driver_number': 81, 'team_name': 'McLaren'},
        # Add any other drivers here
    ]}

    # Apply the backup team name if the current team name is NaN
    drivers_df['team_name'] = drivers_df.apply(lambda x: backup_team_names_dict.get(x['driver_number'], x['team_name']) if pd.isna(x['team_name']) else x['team_name'], axis=1)

    team_colors = {
        # This year's teams with their colors
        'Red Bull Racing': '#3671C6',
        'Williams': '#64C4FF',
        'RB': '#6692FF',  # Assuming as a variant of Red Bull Racing, kept as per your data
        'McLaren': '#FF8000',
        'Alpine': '#FF87BC',
        'Aston Martin': '#229971',
        'Ferrari': '#E8002D',
        'Haas F1 Team': '#B6BABD',
        'Kick Sauber': '#52E3C2',  # Placeholder, as per your data
        'Mercedes': '#00D2BE',

        # Last year's teams (if any were different or missing)
        # Placeholder values for teams not in this year's list
        'AlphaTauri': '#5E8FAA',  # Assuming this was a team from last year you want to include
        'Alfa Romeo': '#C92D4B',  # Assuming this was the color from last year you want to include
        # Add any other teams from last year that are not in this year's list with their respective colors
    }
    # Replace team color codes directly using the team_colors dictionary, using '#FFFFFF' if the team is not found
    drivers_df['team_colour'] = drivers_df['team_name'].apply(lambda x: team_colors.get(x, '#FFFFFF'))

    drivers_df['headshot'] = drivers_df['headshot_url'].apply(lambda x: f"![]({x})")
    drivers_columns = [
                          {'name': 'driver_number', 'id': 'driver_number'},
                          {'name': 'headshot', 'id': 'headshot', 'presentation': 'markdown'}
                      ] + [{'name': i, 'id': i} for i in drivers_df.columns if
                           i not in ['driver_number', 'headshot', 'headshot_url']]

    return drivers_df, drivers_columns


def process_race_control_data(race_control_data):
    race_control_df = pd.DataFrame(race_control_data)
    race_control_df['timestamp'] = pd.to_datetime(race_control_df['date']).astype('int64') / 10 ** 9
    race_control_df['timestamp'] = race_control_df['timestamp'].astype(float)
    race_control_df = race_control_df.drop(columns=['meeting_key', 'session_key'])
    race_control_df['date'] = race_control_df['date'].str.slice(11, 23)
    return race_control_df


def process_weather_data(weather_data):
    weather_df = pd.DataFrame(weather_data)
    weather_df['timestamp'] = pd.to_datetime(weather_df['date'], format='ISO8601').astype('int64') / 10 ** 9
    weather_df['timestamp'] = weather_df['timestamp'].astype(float)

    return weather_df


def process_positions_data(positions_data):
    positions_df = pd.DataFrame(positions_data)
    positions_df['timestamp'] = pd.to_datetime(positions_df['date'], format='ISO8601').astype('int64') / 10 ** 9
    positions_df['timestamp'] = positions_df['timestamp'].astype(float)
    positions_df['date'] = pd.to_datetime(positions_df['date'], errors='coerce')
    positions_df = positions_df.sort_values(by='date')
    return positions_df


def process_laps_data(laps_data, drivers_df):
    laps_df = pd.DataFrame(laps_data)
    # Convert segments arrays to comma-separated strings
    try:
        if 'segments_sector_1' in laps_df.columns:
            laps_df['segments_sector_1'] = laps_df['segments_sector_1'].apply(lambda x: ', '.join(map(str, x)))
        if 'segments_sector_2' in laps_df.columns:
            laps_df['segments_sector_2'] = laps_df['segments_sector_2'].apply(lambda x: ', '.join(map(str, x)))
        if 'segments_sector_3' in laps_df.columns:
            laps_df['segments_sector_3'] = laps_df['segments_sector_3'].apply(
                lambda x: ', '.join(map(str, x)) if x else '')

        # laps_df = laps_df[laps_df['date_start'].notna()]

        laps_df = laps_df.drop(
            columns=['segments_sector_1', 'segments_sector_2', 'segments_sector_3', 'meeting_key', 'session_key',
                     'i1_speed', 'i2_speed', 'st_speed'])
        # print(laps_df['date_start'])
        for i, date_str in enumerate(laps_df['date_start']):
            # Check if date_str is not None and has fractional seconds
            if date_str is not None and len(date_str) == 19:  # Length 19 indicates no fractional seconds
                # Add default fractional seconds
                date_str += ".000000"
                # Update the DataFrame with the new date_str
                laps_df.loc[i, 'date_start'] = date_str
        laps_df['timestamp'] = pd.to_datetime(laps_df['date_start'], format='ISO8601').astype('int64') / 10 ** 9
        # print(laps_df['timestamp'])
        laps_df['timestamp'] = laps_df['timestamp'].astype(float)
        # print(laps_df['timestamp'])
        laps_df['date_start'] = laps_df['date_start'].str.slice(11, 23)
        # print(laps_df['date_start'])


        laps_df['lap_duration_display'] = laps_df['lap_duration'].apply(
            lambda x: f"{int(x) // 60}:{x % 60:06.3f}" if not pd.isnull(x) and x != '' else np.nan)
        # print(laps_df['lap_duration'])
        merged_laps_df = pd.merge(laps_df, drivers_df[['driver_number', 'full_name', 'team_name']],
                                  on='driver_number',
                                  how='left')
        laps_df = merged_laps_df
        # print(laps_df.columns)
        new_column_order = ['lap_number', 'full_name', 'team_name'] + [col for col in laps_df.columns if
                                                                       col not in ['lap_number', 'full_name',
                                                                                   'team_name']]

        laps_df = laps_df[new_column_order]
        laps_df = laps_df.dropna(subset=['lap_duration'])
        fastest_laps_df = laps_df
        fastest_laps_df['lap_duration'] = fastest_laps_df['lap_duration'].astype(str)
        laps_df['lap_duration'] = laps_df['lap_duration'].astype(float)
        # print(laps_df['lap_duration'])
        all_laps_df = pd.DataFrame()
        all_laps_df = laps_df
        fastest_lap_indices = laps_df.groupby('driver_number')['lap_duration'].idxmin()
        # Use these indices to filter the DataFrame
        laps_df = laps_df.loc[fastest_lap_indices]
        laps_df = laps_df.sort_values(by=['lap_duration'], ascending=True)
        # print(laps_df['lap_duration'])
        laps_df['lap_duration_display'] = laps_df['lap_duration'].apply(
            lambda x: f"{int(x) // 60}:{x % 60:06.3f}" if not pd.isnull(x) and x != '' else np.nan)
        laps_df = laps_df.drop(columns=['lap_duration', 'is_pit_out_lap'])
        laps_df = laps_df.rename(columns={'lap_duration_display': 'lap_duration'})
        # print(laps_df.columns)


    except Exception as e:
        print(f"An error occurred: {e}. Skipping operation.")
        # fastest_laps_df = laps_df.drop(columns=['date_start', 'is_pit_out_lap'])
        # driver_position_plot = plot_driver_positions_over_time(positions_df)
    return laps_df, fastest_laps_df, all_laps_df