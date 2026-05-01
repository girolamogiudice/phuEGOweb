from pathlib import Path


class ExperimentPaths:
    """
    Runtime filesystem contract for a single experiment.

    submission_root : results/<submission_uuid>
    experiment_name : "EGFR"
    propagation     : 0.85
    """

    def __init__(self, submission_root, experiment_name, propagation):
        self.submission_root = Path(submission_root)
        self.exp_root = self.submission_root / experiment_name
        self.prop_root = self.exp_root / str(propagation)

        self.logs = self.prop_root / "logs"
        self.increased = self.prop_root / "increased"
        self.decreased = self.prop_root / "decreased"

        self.rwr_scores = self.exp_root / "rwr_scores.txt"
        self.pvalues = self.exp_root / "pvalues.txt"
        self.experiment_manifest = self.exp_root / "experiment_manifest.json"
        self.run_manifest = self.prop_root / "manifest.json"

    def ensure(self):
        for p in [
            self.exp_root,
            self.prop_root,
            self.logs,
            self.increased,
            self.decreased,
        ]:
            p.mkdir(parents=True, exist_ok=True)
        
    def to_dict(self):
        return {
            "experiment_root": str(self.exp_root),
            "propagation_root": str(self.prop_root),
        }
