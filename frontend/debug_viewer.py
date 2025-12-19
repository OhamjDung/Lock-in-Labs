import streamlit as st
import json
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import os

# --- Page Config ---
st.set_page_config(
    page_title="Skill Tree Viewer",
    page_icon="🌳",
    layout="wide"
)

# --- Helper Functions ---
def load_data(filepath="data/skill_tree_debug_output.json"):
    """Loads the skill tree data from the specified JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Error: The file was not found at '{filepath}'. Please make sure the test script has been run.")
        return None

def create_interactive_graph(skill_tree_data):
    """Creates an interactive Pyvis graph from the skill tree data."""
    nodes_data = skill_tree_data.get("nodes", [])
    if not nodes_data:
        return None

    # Create network
    net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white", notebook=True, directed=True)

    # Set physics options for a better layout (more spacing)
    net.set_options(
        """
        var options = {
          "layout": {
            "hierarchical": {
              "enabled": true,
              "levelSeparation": 220,
              "nodeSpacing": 220,
              "treeSpacing": 260,
              "direction": "UD",
              "sortMethod": "directed"
            }
          },
          "physics": {
            "enabled": true,
            "hierarchicalRepulsion": {
              "centralGravity": 0.0,
              "springLength": 200,
              "springConstant": 0.03,
              "nodeDistance": 220,
              "damping": 0.15
            },
            "minVelocity": 0.5,
            "solver": "hierarchicalRepulsion"
          }
        }
        """
    )

    # Define styles for different node types
    styles = {
        "Goal": {"color": "#a3d9a5", "shape": "box", "font": {"color": "#000000"}},
        "Sub-Skill": {"color": "#a9d1f7", "shape": "ellipse", "font": {"color": "#000000"}},
        "Habit": {"color": "#f7d5a9", "shape": "diamond", "font": {"color": "#000000"}},
    }

    # Add nodes to the graph
    for node in nodes_data:
        node_id = node["id"]
        node_name = node["name"]
        node_type = node["type"]
        style = styles.get(node_type, {"color": "lightgrey"})

        title = f"""
        <b>ID:</b> {node['id']}<br>
        <b>Type:</b> {node['type']}<br>
        <b>Pillar:</b> {node['pillar']}<br>
        <b>XP:</b> {node['xp_reward']}<br>
        <b>Reps to Master:</b> {node.get('required_completions', 'N/A')}<br>
        <b>Description:</b> {node.get('description', 'N/A')}
        """

        net.add_node(node_id, label=node_name, title=title, **style)

    # Add edges (prerequisites)
    for node in nodes_data:
        node_id = node["id"]
        for prereq_id in node.get("prerequisites", []):
            if any(n["id"] == prereq_id for n in nodes_data):
                net.add_edge(prereq_id, node_id)

    return net

# --- Main App ---
st.title("🌳 Interactive Skill Tree Visualizer")
st.write("Pan, zoom, and drag the nodes to explore the skill tree. Hover over a node to see its details.")

# Load the data
data = load_data()

if data:
    # Create and display the interactive graph
    st.header("Generated Skill Graph")
    net = create_interactive_graph(data)
    if net:
        # Save network to a temporary HTML file
        temp_html_path = "temp_network.html"
        net.save_graph(temp_html_path)
        
        # Load HTML file and display in Streamlit
        with open(temp_html_path, 'r', encoding='utf-8') as f:
            html_code = f.read()
        components.html(html_code, height=800)
        
        # Clean up the temporary file
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
    else:
        st.warning("No nodes found in the data to build a graph.")

    # Display the raw data in a table
    st.header("Raw Node Data")
    df = pd.json_normalize(data, "nodes")
    st.dataframe(df)
