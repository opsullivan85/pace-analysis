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
            self.outpath = self.rosbag_path.name.with_suffix('.png')
        self.outpath = Path(src.__file__).parent.parent / "images" / self.outpath

def plot_topics(settings: PlotSettings) -> None:
    topics = settings.label_map.keys()

    bag = rosbag.Bag(str(settings.rosbag_path))
    topic_data = {topic: [] for topic in topics}
    time_data = {topic: [] for topic in topics}
    t_zero = None

    # Determine time window for reading messages
    t_zero = None
    if settings.graph_range is not None:
        # Find t_zero first to compute absolute start/end times
        for topic, msg, t in bag.read_messages(topics=topics):
            t_zero = t.to_sec()
            break
        if t_zero is not None:
            start_time = rospy.Time.from_sec(t_zero + settings.graph_range[0])
            end_time = rospy.Time.from_sec(t_zero + settings.graph_range[1])
        else:
            # No messages found, skip plotting
            bag.close()
            print(f"No messages found in topics {topics} of bag {settings.rosbag_path.name}.")
            return
        # Re-open bag to reset iterator
        bag.close()
        bag = rosbag.Bag(str(settings.rosbag_path))
        msg_iter = bag.read_messages(topics=topics, start_time=start_time, end_time=end_time)
    else:
        msg_iter = bag.read_messages(topics=topics)

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

    if not any(topic_data[topic] for topic in topics):
        print(f"No numeric data found in topics {topics} of bag {settings.rosbag_path.name}.")

    bag.close()

    plt.figure(figsize=(5, 3))
    for topic in topics:
        topic_label = settings.label_map[topic] if topic in settings.label_map else topic
        if topic_data[topic]:
            if isinstance(topic_data[topic][0], (list, tuple)):
                arr = topic_data[topic]
                arr = [list(a) for a in arr]
                arr = list(zip(*arr))
                labels = [f"[{i}]" for i in range(len(arr))]
                for i, dim in enumerate(arr):
                    plt.plot(time_data[topic], dim, label=f"{topic_label} {labels[i]}")
            else:
                plt.plot(time_data[topic], topic_data[topic], label=topic_label)
    
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