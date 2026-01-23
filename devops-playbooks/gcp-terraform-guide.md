# Развертывание базовой инфраструктуры в GCP через Terraform

В данной инструкции описано, как создать проект, сеть (VPC) и один инстанс Compute Engine в Google Cloud Platform.

### Предварительные условия
1. Установлен [Google Cloud SDK](https://cloud.google.com/sdk).
2. Настроен доступ через `gcloud auth application-default login`.
3. Создан проект в GCP Console.

### Описание ресурсов

| Ресурс | Описание | Тип |
| :--- | :--- | :--- |
| `google_compute_network` | Основная виртуальная сеть | VPC |
| `google_compute_instance` | Виртуальная машина | VM |
| `google_storage_bucket` | Бакет для хранения данных | Storage |

### Пример конфигурации `main.tf`

```hcl
provider "google" {
  project = "my-devops-project"
  region  = "us-central1"
}

resource "google_compute_network" "vpc_network" {
  name = "terraform-network"
}

resource "google_compute_instance" "vm_instance" {
  name         = "terraform-instance"
  machine_type = "f1-micro"
  zone         = "us-central1-c"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.name
    access_config {
    }
  }
}
```

### Запуск
1. `terraform init`
2. `terraform plan`
3. `terraform apply`

> [!NOTE]
> Не забудьте включить Compute Engine API в вашем проекте перед запуском Terraform.

![Схема ресурсов в GCP](path/to/gcp_resources.png)
