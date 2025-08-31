from __future__ import annotations
import src
import rospy
from pathlib import Path
import rosbag
import matplotlib.pyplot as plt
import scienceplots
from multiprocessing import Pool
from dataclasses import dataclass, field
import yaml
import logging
import re
import random

logging.getLogger('matplotlib.font_manager').disabled = True

plt.style.use(['ieee', 'grid'])

@dataclass
class PlotSettings:
    rosbag_path: Path
    topics: list[str]
    label_map: dict[str, str]
    outpath: Path = None
    slip_regions: list[tuple[float, float]] = field(default_factory=list)
    graph_range: tuple[float, float] = None  # Changed default to None
    legend_loc: str = "best"
    epoc_time: bool = False

    def __post_init__(self):
        if self.outpath is None:
            random_int = random.randint(100000000,999999999)
            self.outpath = (
                Path(src.__file__).parent.parent / "images" / f"{self.rosbag_path.stem}--{random_int}"
            ).with_suffix(".png")
        self.outpath = Path(src.__file__).parent.parent / "images" / self.outpath

def parse_topic_with_index(topic_key: str) -> tuple[str, int | None]:
    """Parse topic key to extract topic name and optional index.
    
    Args:
        topic_key: String like "/topic/name" or "/topic/name[2]"
        
    Returns:
        Tuple of (topic_name, index) where index is None if not specified
    """
    match = re.match(r'^(.+?)\[(\d+)\]$', topic_key)
    if match:
        topic_name = match.group(1)
        index = int(match.group(2))
        return topic_name, index
    else:
        return topic_key, None

def plot_topics(settings: PlotSettings) -> None:
    # Parse label_map keys to extract actual topics and their indices
    topic_info = {}  # topic_name -> list of (index, label)
    actual_topics = set()
    
    for topic_key, label in settings.label_map.items():
        topic_name, index = parse_topic_with_index(topic_key)
        actual_topics.add(topic_name)
        if topic_name not in topic_info:
            topic_info[topic_name] = []
        topic_info[topic_name].append((index, label))

    bag = rosbag.Bag(str(settings.rosbag_path))
    topic_data = {topic: [] for topic in actual_topics}
    time_data = {topic: [] for topic in actual_topics}
    t_zero = None

    # Determine time window for reading messages
    t_zero = None
    if settings.graph_range is not None:
        # Find t_zero first to compute absolute start/end times
        if not settings.epoc_time:
            for topic, msg, t in bag.read_messages(topics=actual_topics):
                t_zero = t.to_sec()
                break
            if t_zero is not None:
                if settings.epoc_time:
                    start_time = rospy.Time.from_sec(t_zero + settings.graph_range[0])
                    end_time = rospy.Time.from_sec(t_zero + settings.graph_range[1])
            else:
                # No messages found, skip plotting
                bag.close()
                print(f"No messages found in topics {actual_topics} of bag {settings.rosbag_path.name}.")
                return
            # Re-open bag to reset iterator
            bag.close()
            bag = rosbag.Bag(str(settings.rosbag_path))
            msg_iter = bag.read_messages(topics=actual_topics, start_time=start_time, end_time=end_time)
        else:
            start_time = rospy.Time.from_sec(settings.graph_range[0])
            end_time = rospy.Time.from_sec(settings.graph_range[1])
            msg_iter = bag.read_messages(topics=actual_topics, start_time=start_time, end_time=end_time)
    else:
        msg_iter = bag.read_messages(topics=actual_topics)

    if settings.epoc_time:
        t_zero = 0.0
        
    for topic, msg, t in msg_iter:
        if t_zero is None:
            t_zero = t.to_sec()
            print(f"t_zero set to {t_zero} for bag {settings.rosbag_path.name}")
        value = getattr(msg, 'data', None)
        dt = t.to_sec() - t_zero
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            topic_data[topic].append(list(value))
        else:
            topic_data[topic].append(value)
        time_data[topic].append(dt)

    if not any(topic_data[topic] for topic in actual_topics):
        print(f"No numeric data found in topics {actual_topics} of bag {settings.rosbag_path.name}.")

    bag.close()

    plt.figure(figsize=(5, 3))
    
    # Plot data according to the label_map specifications
    for topic_name, index_label_pairs in topic_info.items():
        if not topic_data[topic_name]:
            continue
            
        # Check if data is array-like
        if isinstance(topic_data[topic_name][0], (list, tuple)):
            # Data is multi-dimensional
            arr = topic_data[topic_name]
            arr = [list(a) for a in arr]
            arr = list(zip(*arr))
            
            for index, label in index_label_pairs:
                if index is None:
                    # Plot all dimensions with auto-generated labels
                    labels = [f"[{i}]" for i in range(len(arr))]
                    for i, dim in enumerate(arr):
                        plt.plot(time_data[topic_name], dim, label=f"{label} {labels[i]}")
                else:
                    # Plot only the specified index
                    if index < len(arr):
                        plt.plot(time_data[topic_name], arr[index], label=label)
                    else:
                        print(f"Warning: Index {index} out of range for topic {topic_name} (has {len(arr)} dimensions)")
        else:
            # Data is scalar
            for index, label in index_label_pairs:
                if index is None:
                    # Plot the scalar data
                    plt.plot(time_data[topic_name], topic_data[topic_name], label=label)
                else:
                    print(f"Warning: Index {index} specified for scalar topic {topic_name}")
    
    # draw an opaque red rectangle for slip regions
    for i, slip_region in enumerate(settings.slip_regions):
        label = None
        if i == 0:
            label = 'Slip Regions' if len(settings.slip_regions) > 1 else 'Slip Region'
        plt.axvspan(slip_region[0], slip_region[1], color='red', alpha=0.3, label=label)
    
    plt.xlabel("Time [s]")
    if settings.graph_range is not None:
        plt.xlim(settings.graph_range)
    plt.ylabel("Value")
    plt.legend(loc=settings.legend_loc if settings.legend_loc else 'best')
    plt.tight_layout()
    plt.savefig(settings.outpath)
    plt.close()

def process_bag(settings: PlotSettings) -> None:
    try:
        with rosbag.Bag(str(settings.rosbag_path)) as bag:
            if bag.get_message_count() == 0:
                print(f"Skipping empty bag file: {settings.rosbag_path.name}")
                return
        print(f"Processing {settings.rosbag_path.name}")
        plot_topics(settings)
        print(f"Done processing {settings.rosbag_path.name}")
    except rosbag.bag.ROSBagException:
        print(f"Skipping invalid/corrupted bag file: {settings.rosbag_path.name}")

def load_settings_from_yaml(yaml_path: Path, data_dir: Path) -> list[PlotSettings]:
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    settings_list = []
    configs = config if isinstance(config, list) else [config]
    for entry in configs:
        rosbag_path = data_dir / entry["rosbag_path"]
        settings = PlotSettings(
            rosbag_path=rosbag_path,
            topics=entry.get("topics", []),
            label_map=entry.get("label_map", {}),
            outpath=entry.get("outpath", None),
            slip_regions=[tuple(region) for region in entry.get("slip_regions", [])],
            graph_range=tuple(entry["graph_range"]) if "graph_range" in entry else None,  # Updated to None if missing
            legend_loc=entry.get("legend_loc", "best"),
            epoc_time=entry.get("epoc_time", False)
        )
        settings_list.append(settings)
    return settings_list

def main() -> None:
    (Path(src.__file__).parent.parent / "images").mkdir(exist_ok=True)
    # remove contentant of images directory
    for img_file in (Path(src.__file__).parent.parent / "images").glob("*.png"):
        img_file.unlink()

    data_dir = Path(src.__file__).parent.parent / "data"
    settings_dir = Path(src.__file__).parent.parent / "plot_settings"
    yamls = list(settings_dir.glob("*.yaml"))

    # Collect PlotSettings from all yaml files
    settings_list = []
    for yaml_file in yamls:
        settings_list.extend(load_settings_from_yaml(yaml_file, data_dir))

    # print(settings_list)
    with Pool() as pool:
        pool.map(process_bag, settings_list)

if __name__ == "__main__":
    main()