from evaluate import run_models_on_files, pretty_print_predictions


if __name__ == "__main__":
    df_preds, labels = run_models_on_files(
        "data/hypoxia/10/bpm/20250908-07400002_1.csv",
        "data/hypoxia/10/uterus/20250908-07400002_2.csv",
        sampling_rate=4,
        threshold=0.5,
    )
    # print(df_preds[[*(f"proba_{l}" for l in labels), *(f"pred_{l}" for l in labels)]])
    print(pretty_print_predictions(df_preds, labels))