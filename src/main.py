from __future__ import annotations
import src
import rospy
from pathlib import Path
import rosbag
import matplotlib.pyplot as plt
import scienceplots
from multiprocessing import Pool

def plot_topics(rosbag_path: Path, topics: list[str], label_map: dict[str, str], outpath: Path) -> None:
    plt.style.use(['ieee', 'grid'])
    plt.rcParams['font.serif'] = ['Times New Roman']

    bag = rosbag.Bag(str(rosbag_path))
    topic_data = {topic: [] for topic in topics}
    time_data = {topic: [] for topic in topics}
    t_zero = None

    for topic, msg, t in bag.read_messages(topics=topics):
        if t_zero is None:
            t_zero = t.to_sec()
        value = getattr(msg, 'data', None)
        if value is not None:
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                topic_data[topic].append(list(value))
            else:
                topic_data[topic].append(value)
            time_data[topic].append(t.to_sec() - t_zero)
        else:
            if hasattr(msg, 'x') and hasattr(msg, 'y') and hasattr(msg, 'z'):
                topic_data[topic].append([msg.x, msg.y, msg.z])
                time_data[topic].append(t.to_sec())
    
    if not any(topic_data[topic] for topic in topics):
        print(f"No numeric data found in topics {topics} of bag {rosbag_path.name}.")

    bag.close()

    plt.figure(figsize=(5, 3))
    for topic in topics:
        topic_label = label_map[topic] if topic in label_map else topic
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
    plt.xlabel("Time [s]")
    plt.ylabel("Value")
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def process_bag(args):
    bag_path, topics, label_map, outpath = args
    try:
        with rosbag.Bag(str(bag_path)) as bag:
            if bag.get_message_count() == 0:
                print(f"Skipping empty bag file: {bag_path.name}")
                return
        print(f"Processing {bag_path.name}")
        plot_topics(bag_path, topics, label_map, outpath)
    except rosbag.bag.ROSBagException:
        print(f"Skipping invalid/corrupted bag file: {bag_path.name}")

def main() -> None:
    (Path(src.__file__).parent.parent / "images").mkdir(exist_ok=True)
    # remove contentant of images directory
    for img_file in (Path(src.__file__).parent.parent / "images").glob("*.png"):
        img_file.unlink()

    data_dir = Path(src.__file__).parent.parent / "data"
    rosbags = list(data_dir.glob("*.bag"))

    if not rosbags:
        rospy.logwarn("No ROS bag files found in the data directory.")
        return

    # topics = ["/contact_estimation/leg1_contact"]  # Replace with actual topics you want to plot
    label_map = {
        "/contact_estimation/leg1_contact": "Leg 1 Contact",
        "/contact_estimation/leg2_contact": "Leg 2 Contact",
        "/contact_estimation/leg3_contact": "Leg 3 Contact",
        "/contact_estimation/leg4_contact": "Leg 4 Contact",
    }
    topics = list(label_map.keys())
    args_list = [
        (
            bag_path,
            topics,
            label_map,
            (Path(src.__file__).parent.parent / "images" / bag_path.stem).with_suffix('.png')
        )
        for bag_path in rosbags
    ]

    with Pool() as pool:
        pool.map(process_bag, args_list)

if __name__ == "__main__":
    main()