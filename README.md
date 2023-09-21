## Contribution

Contribution [guide](CONTRIBUTING.md) should be respected.

When you add charts to `stable/` directory, you need to add/update you charts within `repo` directory.

### Package your chart

```bash
helm package -d repo/ $YOUR_CHART_PATH/
```

*Add the option `-u` when the package has dependencies*
*Change `repo/` with `repo-incubator` for unstable packages.*

### Index your chart

```bash
helm repo index repo/
```
