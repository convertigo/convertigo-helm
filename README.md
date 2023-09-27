
### Stable repository

Charts are packaged and stored under `repo/` directory. To use this github repository as helm repository you need to run these commands:

```bash
$ helm repo add convertigo 'https://raw.githubusercontent.com/convertigo/convertigo-helm/master/repo'
$ helm repo update
```


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
