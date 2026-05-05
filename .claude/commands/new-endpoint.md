# Skill: nuevo endpoint DRF

Crea un endpoint completo en un servicio Django siguiendo el patrón de RiskCore. Uso: `/new-endpoint [servicio] [recurso]`.

Ejemplo: `/new-endpoint policy-service coverage`

## Pasos obligatorios — en este orden

1. **Model** en `apps/[dominio]/models.py`
   - UUID como primary key (`default=uuid.uuid4`)
   - `created_at = models.DateTimeField(auto_now_add=True)`
   - `updated_at = models.DateTimeField(auto_now=True)` si aplica
   - Meta con ordering, índices relevantes
   - `__str__` útil para el admin

2. **Migración** — crear con `python manage.py makemigrations`

3. **Serializer** en `apps/[dominio]/serializers.py`
   - Separar serializer de lectura y de escritura si los campos difieren
   - Validaciones en `validate_[campo]` o `validate()`
   - Nunca exponer campos internos o sensibles

4. **Service** en `apps/[dominio]/services.py`
   - TODA la lógica de negocio aquí
   - El service recibe datos validados del serializer
   - El service lanza excepciones de dominio (`ValidationError`, custom exceptions)
   - Si hay evento Kafka → llamar al producer aquí

5. **ViewSet** en `apps/[dominio]/views.py`
   - Thin: validar request, llamar service, devolver response
   - Usar `get_object_or_404` para lookups
   - Actions custom con `@action(detail=True, methods=["post"])`
   - Permisos con `permission_classes`

6. **URL** en `apps/[dominio]/urls.py`
   - Registrar en el router existente

7. **Kafka event** (si aplica) en `apps/[dominio]/events.py`
   - Schema estándar: `event_id`, `event_type`, `occurred_at`, `service`, `data`
   - Llamar a `producer.flush()` después de `produce()`

8. **Admin** en `apps/[dominio]/admin.py`
   - Registrar con `@admin.register` usando django-unfold
   - Añadir `list_display`, `list_filter`, `search_fields`

9. **Tests** en `apps/[dominio]/tests/`
   - `test_services.py` — unit tests del service (Kafka mockeado)
   - `test_views.py` — integration tests con `@pytest.mark.django_db`
   - Usar `factory-boy` para crear fixtures

## Checklist de calidad antes de entregar

- [ ] `ruff check apps/[dominio]/` sin errores
- [ ] `mypy apps/[dominio]/` sin errores de tipo
- [ ] Tests pasan: `pytest apps/[dominio]/tests/ -v`
- [ ] Endpoint documentado automáticamente en `/api/schema/swagger-ui/`
- [ ] Errores devuelven formato estándar `{"error": {"code": ..., "message": ..., "details": ...}, "request_id": ...}`
