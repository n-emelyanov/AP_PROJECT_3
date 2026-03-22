"""
Нагрузочные тесты для API сокращения ссылок
Запуск: locust -f locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between
import random
import string


def random_url():
    """Генерация случайного URL для тестирования"""
    domains = ["google.com", "example.com", "test.com", "demo.org"]
    path = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f"https://{random.choice(domains)}/{path}"


class ShortLinkUser(HttpUser):
    """Нагрузочный пользователь"""
    
    # Ожидание между запросами 0.5-1.5 секунды
    wait_time = between(0.5, 1.5)
    
    def on_start(self):
        """При старте создаем список для хранения созданных ссылок"""
        self.codes = []
    
    @task(3)
    def create_link(self):
        """Создание короткой ссылки (вес 3)"""
        url = random_url()
        with self.client.post(
            "/links/shorten",
            json={"original_url": url},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.codes.append(data["short_code"])
                response.success()
            else:
                response.failure(f"Create failed: {response.status_code}")
    
    @task(5)
    def redirect(self):
        """Переход по ссылке (вес 5)"""
        if not self.codes:
            return
        
        code = random.choice(self.codes)
        with self.client.get(
            f"/links/{code}",
            follow_redirects=False,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Redirect failed: {response.status_code}")
    
    @task(2)
    def get_stats(self):
        """Получение статистики (вес 2)"""
        if not self.codes:
            return
        
        code = random.choice(self.codes)
        with self.client.get(
            f"/links/{code}/stats",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stats failed: {response.status_code}")
    
    @task(1)
    def delete_link(self):
        """Удаление ссылки (вес 1)"""
        if not self.codes:
            return
        
        # Удаляем случайную ссылку из списка
        if self.codes:
            code = self.codes.pop(random.randint(0, len(self.codes) - 1))
            with self.client.delete(
                f"/links/{code}",
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Delete failed: {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Проверка здоровья сервиса (вес 1)"""
        with self.client.get(
            "/health",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")