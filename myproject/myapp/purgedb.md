BEGIN;

DELETE FROM myapp_registrocomision;
DELETE FROM myapp_pago;
DELETE FROM myapp_notificacion;
DELETE FROM myapp_auditoriasistema;
DELETE FROM myapp_reclamacion;
DELETE FROM myapp_factura;
DELETE FROM myapp_contratocolectivo_afiliados_colectivos;
DELETE FROM myapp_contratoindividual;
DELETE FROM myapp_contratocolectivo;
DELETE FROM myapp_afiliadoindividual;
DELETE FROM myapp_afiliadocolectivo;
DELETE FROM myapp_intermediario_usuarios;
DELETE FROM myapp_intermediario;
DELETE FROM myapp_tarifa;
DELETE FROM myapp_licenseinfo;

-- Para borrar TODOS los usuarios (incluyendo superusuario):
DELETE FROM myapp_usuario_groups;
DELETE FROM myapp_usuario_user_permissions;
DELETE FROM myapp_usuario;

-- ALTERNATIVA: Para borrar todos los usuarios EXCEPTO el superusuario con email 'jacr7887@gmail.com':
-- DELETE FROM myapp_usuario_groups WHERE usuario_id NOT IN (SELECT id FROM myapp_usuario WHERE email = 'jacr7887@gmail.com');
-- DELETE FROM myapp_usuario_user_permissions WHERE usuario_id NOT IN (SELECT id FROM myapp_usuario WHERE email = 'jacr7887@gmail.com');
-- DELETE FROM myapp_usuario WHERE email != 'jacr7887@gmail.com';

COMMIT;




para crear datos

python manage.py seed_db --users 100 --intermediarios 20 --afiliados_ind 200 --afiliados_col 50 --tarifas 30 --contratos_ind 150 --contratos_col 80 --facturas 500 --reclamaciones 100 --pagos 400 --notificaciones 100 --auditorias 100 --igtf_chance 30