CREATE DATABASE IF NOT EXISTS `407_courtyards`;
USE `407_courtyards`;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `staff_schedule`;
DROP TABLE IF EXISTS `work_orders`;
DROP TABLE IF EXISTS `maintenance_requests`;
DROP TABLE IF EXISTS `payments`;
DROP TABLE IF EXISTS `leases`;
DROP TABLE IF EXISTS `applications`;
DROP TABLE IF EXISTS `units`;
DROP TABLE IF EXISTS `floorplans`;
DROP TABLE IF EXISTS `users`;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `role` ENUM('Admin', 'Resident', 'Staff') NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`)
);

CREATE TABLE `floorplans` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `rent` INT NOT NULL,
  `bedrooms` INT NOT NULL,
  `bathrooms` INT NOT NULL,
  `size` INT NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `units` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `building` VARCHAR(20) NOT NULL,
  `unit_number` VARCHAR(20) NOT NULL,
  `floorplan_id` INT NOT NULL,
  `status` ENUM('Available', 'Occupied', 'Reserved', 'Maintenance') NOT NULL DEFAULT 'Available',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_units_unit_number` (`unit_number`),
  CONSTRAINT `fk_units_floorplan`
    FOREIGN KEY (`floorplan_id`) REFERENCES `floorplans` (`id`)
);

CREATE TABLE `applications` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `application_code` VARCHAR(20) NOT NULL,
  `applicant_name` VARCHAR(255) NOT NULL,
  `applicant_email` VARCHAR(255) NOT NULL,
  `applicant_phone` VARCHAR(25) NOT NULL,
  `floorplan_id` INT NOT NULL,
  `desired_move_in` DATE NOT NULL,
  `status` ENUM('Pending', 'Approved', 'Denied', 'Deposit Paid') NOT NULL DEFAULT 'Pending',
  `submitted_at` DATETIME NOT NULL,
  `assigned_unit_id` INT DEFAULT NULL,
  `notes` TEXT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_applications_code` (`application_code`),
  CONSTRAINT `fk_applications_floorplan`
    FOREIGN KEY (`floorplan_id`) REFERENCES `floorplans` (`id`),
  CONSTRAINT `fk_applications_unit`
    FOREIGN KEY (`assigned_unit_id`) REFERENCES `units` (`id`)
);

CREATE TABLE `leases` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lease_code` VARCHAR(20) NOT NULL,
  `resident_user_id` INT NOT NULL,
  `unit_id` INT NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `monthly_rent` DECIMAL(10, 2) NOT NULL,
  `security_deposit` DECIMAL(10, 2) NOT NULL,
  `status` ENUM('Pending', 'Active', 'Ended') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_leases_code` (`lease_code`),
  CONSTRAINT `fk_leases_user`
    FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_leases_unit`
    FOREIGN KEY (`unit_id`) REFERENCES `units` (`id`)
);

CREATE TABLE `payments` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `payment_code` VARCHAR(20) NOT NULL,
  `lease_id` INT NOT NULL,
  `resident_user_id` INT NOT NULL,
  `amount` DECIMAL(10, 2) NOT NULL,
  `method` ENUM('Card', 'Bank Transfer', 'Cash', 'Check') NOT NULL,
  `status` ENUM('Pending', 'Paid', 'Failed', 'Resolved') NOT NULL,
  `payment_date` DATE DEFAULT NULL,
  `confirmation_number` VARCHAR(30) DEFAULT NULL,
  `notes` TEXT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payments_code` (`payment_code`),
  CONSTRAINT `fk_payments_lease`
    FOREIGN KEY (`lease_id`) REFERENCES `leases` (`id`),
  CONSTRAINT `fk_payments_user`
    FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`)
);

CREATE TABLE `maintenance_requests` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `request_code` VARCHAR(20) NOT NULL,
  `resident_user_id` INT NOT NULL,
  `lease_id` INT NOT NULL,
  `category` VARCHAR(100) NOT NULL,
  `issue_title` VARCHAR(255) NOT NULL,
  `description` TEXT NOT NULL,
  `priority` ENUM('Low', 'Medium', 'High', 'Urgent') NOT NULL,
  `status` ENUM('Open', 'Assigned', 'In Progress', 'Closed') NOT NULL DEFAULT 'Open',
  `created_at` DATETIME NOT NULL,
  `attachment_name` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_maintenance_requests_code` (`request_code`),
  CONSTRAINT `fk_requests_user`
    FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_requests_lease`
    FOREIGN KEY (`lease_id`) REFERENCES `leases` (`id`)
);

CREATE TABLE `work_orders` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `work_order_code` VARCHAR(20) NOT NULL,
  `request_id` INT NOT NULL,
  `assigned_staff_id` INT NOT NULL,
  `scheduled_date` DATE DEFAULT NULL,
  `time_window` VARCHAR(50) DEFAULT NULL,
  `status` ENUM('Open', 'Assigned', 'In Progress', 'Closed') NOT NULL,
  `notes` TEXT,
  `closed_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_work_orders_code` (`work_order_code`),
  CONSTRAINT `fk_work_orders_request`
    FOREIGN KEY (`request_id`) REFERENCES `maintenance_requests` (`id`),
  CONSTRAINT `fk_work_orders_staff`
    FOREIGN KEY (`assigned_staff_id`) REFERENCES `users` (`id`)
);

CREATE TABLE `staff_schedule` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `staff_user_id` INT NOT NULL,
  `shift_date` DATE NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `assignment_note` VARCHAR(255),
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_staff_schedule_user`
    FOREIGN KEY (`staff_user_id`) REFERENCES `users` (`id`)
);

INSERT INTO `users` (`id`, `name`, `email`, `password`, `role`) VALUES
  (1, 'Admin1', 'admin1@umd.edu', 'scrypt:32768:8:1$4nAi86mEzIGtrRHj$74bb26a9020de36579155370c9a9eee4953e56eb59fccb75aa9755a758e804a3598a52c6ce67db34250849fa60f80e8cbc6d6b7a0beb60cc6e1e34cdcbd969d4', 'Admin'),
  (2, 'Resident1', 'resident1@umd.edu', 'scrypt:32768:8:1$U2XzVOzxdUaIOl9j$5f3dc6a2cc29f1a82d4d03e7109fd51833a8a80090a7339d14370a0f1acb60047888c9c7ecd42d82e8359aca4fec33c8817869f0f8096c8ab8c5325aeffdad61', 'Resident'),
  (3, 'Staff1', 'staff1@umd.edu', 'scrypt:32768:8:1$TXOwFe5N00ygkQxq$e455c323077ba577624d34b8c611e925ef8df70d2ef3396c351aad7e2cc051c1ae08686f8640581717a46b9b67e1d1c11ed1dc7b7391efab6f4d3f0e5e682b20', 'Staff');

INSERT INTO `floorplans` (`id`, `name`, `rent`, `bedrooms`, `bathrooms`, `size`) VALUES
  (1, '4B/4B', 974, 4, 4, 1189),
  (2, '4B/2B', 888, 4, 2, 1493),
  (3, '2B/2B S', 1082, 2, 2, 785),
  (4, '2B/2B D', 1118, 2, 2, 991);

INSERT INTO `units` (`id`, `building`, `unit_number`, `floorplan_id`, `status`) VALUES
  (1, 'Building 100', '101A', 3, 'Occupied'),
  (2, 'Building 200', '235B', 4, 'Reserved'),
  (3, 'Building 400', '402C', 1, 'Available'),
  (4, 'Building 200', '214C', 2, 'Maintenance');

INSERT INTO `applications` (
  `id`,
  `application_code`,
  `applicant_name`,
  `applicant_email`,
  `applicant_phone`,
  `floorplan_id`,
  `desired_move_in`,
  `status`,
  `submitted_at`,
  `assigned_unit_id`,
  `notes`
) VALUES
  (1, 'A1024', 'Jada Thompson', 'jada@example.com', '240-555-0101', 3, '2026-08-01', 'Pending', '2026-03-10 09:30:00', NULL, 'Waiting on income verification.'),
  (2, 'A1025', 'Marcus Lee', 'marcus@example.com', '240-555-0102', 4, '2026-08-15', 'Approved', '2026-03-10 10:15:00', 2, 'Approved by leasing office.'),
  (3, 'A1026', 'Ava Williams', 'ava@example.com', '240-555-0103', 1, '2026-09-01', 'Deposit Paid', '2026-03-11 11:45:00', 3, 'Deposit received and unit held.');

INSERT INTO `leases` (
  `id`,
  `lease_code`,
  `resident_user_id`,
  `unit_id`,
  `start_date`,
  `end_date`,
  `monthly_rent`,
  `security_deposit`,
  `status`
) VALUES
  (1, 'L2045', 2, 1, '2026-01-01', '2026-12-31', 1082.00, 1082.00, 'Active');

INSERT INTO `payments` (
  `id`,
  `payment_code`,
  `lease_id`,
  `resident_user_id`,
  `amount`,
  `method`,
  `status`,
  `payment_date`,
  `confirmation_number`,
  `notes`
) VALUES
  (1, 'P1001', 1, 2, 1250.00, 'Card', 'Pending', '2026-03-10', 'CNF88214', 'Resident contacted office about delayed processing.'),
  (2, 'P1002', 1, 2, 1300.00, 'Bank Transfer', 'Paid', '2026-03-09', 'CNF88215', 'Payment completed successfully and receipt was sent.'),
  (3, 'P1003', 1, 2, 1180.00, 'Card', 'Failed', '2026-03-08', 'CNF88216', 'Card declined. Resident needs to update payment method.');

INSERT INTO `maintenance_requests` (
  `id`,
  `request_code`,
  `resident_user_id`,
  `lease_id`,
  `category`,
  `issue_title`,
  `description`,
  `priority`,
  `status`,
  `created_at`,
  `attachment_name`
) VALUES
  (1, 'MR501', 2, 1, 'Plumbing', 'Leaking sink', 'Resident reported steady water leaking from the kitchen sink pipe under the cabinet.', 'High', 'Open', '2026-03-11 08:15:00', 'plumbing-photo.jpg'),
  (2, 'MR502', 2, 1, 'HVAC', 'Broken AC', 'Air conditioning unit is running but not cooling the apartment properly.', 'High', 'In Progress', '2026-03-10 09:10:00', 'ac-unit-ticket.pdf'),
  (3, 'MR503', 2, 1, 'Electrical', 'Light fixture out', 'Bedroom ceiling light fixture is not turning on even after bulb replacement.', 'Low', 'Assigned', '2026-03-09 14:35:00', 'electrical-note.docx');

INSERT INTO `work_orders` (
  `id`,
  `work_order_code`,
  `request_id`,
  `assigned_staff_id`,
  `scheduled_date`,
  `time_window`,
  `status`,
  `notes`,
  `closed_at`
) VALUES
  (1, 'WO501', 1, 3, '2026-03-14', '8:00 AM - 10:00 AM', 'Open', 'Assigned to morning plumbing block.', NULL),
  (2, 'WO502', 2, 3, '2026-03-14', '10:00 AM - 12:00 PM', 'In Progress', 'Needs HVAC follow-up after initial inspection.', NULL),
  (3, 'WO503', 3, 3, '2026-03-15', '1:00 PM - 3:00 PM', 'Assigned', 'Bring replacement fixture and tester.', NULL);

INSERT INTO `staff_schedule` (
  `id`,
  `staff_user_id`,
  `shift_date`,
  `start_time`,
  `end_time`,
  `assignment_note`
) VALUES
  (1, 3, '2026-03-14', '08:00:00', '17:00:00', 'Cover Buildings 100 and 200.'),
  (2, 3, '2026-03-15', '08:00:00', '17:00:00', 'Handle scheduled work orders.'),
  (3, 3, '2026-03-16', '09:00:00', '18:00:00', 'Follow-up repairs and new assignments.');
