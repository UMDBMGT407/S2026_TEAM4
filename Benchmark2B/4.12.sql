-- MySQL dump 10.13  Distrib 8.0.45, for macos15 (x86_64)
--
-- Host: localhost    Database: 407_courtyards
-- ------------------------------------------------------
-- Server version	9.6.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '090b0c06-28b4-11f1-8031-88fc58c2c697:1-80';

--
-- Table structure for table `applications`
--

DROP TABLE IF EXISTS `applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `applications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `application_code` varchar(20) NOT NULL,
  `applicant_name` varchar(255) NOT NULL,
  `applicant_email` varchar(255) NOT NULL,
  `applicant_phone` varchar(25) NOT NULL,
  `floorplan_id` int NOT NULL,
  `desired_move_in` date NOT NULL,
  `student_id` varchar(50) NOT NULL,
  `emergency_name` varchar(100) NOT NULL,
  `emergency_phone` varchar(25) NOT NULL,
  `applicant_notes` text,
  `app_id` varchar(512) NOT NULL,
  `app_supp_docs` varchar(512) DEFAULT NULL,
  `status` enum('Pending','Approved','Denied','Deposit Paid') NOT NULL DEFAULT 'Pending',
  `submitted_at` datetime NOT NULL,
  `assigned_unit_id` int DEFAULT NULL,
  `notes` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_applications_code` (`application_code`),
  KEY `fk_applications_floorplan` (`floorplan_id`),
  KEY `fk_applications_unit` (`assigned_unit_id`),
  CONSTRAINT `fk_applications_floorplan` FOREIGN KEY (`floorplan_id`) REFERENCES `floorplans` (`id`),
  CONSTRAINT `fk_applications_unit` FOREIGN KEY (`assigned_unit_id`) REFERENCES `units` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `applications`
--

LOCK TABLES `applications` WRITE;
/*!40000 ALTER TABLE `applications` DISABLE KEYS */;
INSERT INTO `applications` VALUES (1,'A1024','Jada Thompson','jada@example.com','240-555-0101',3,'2026-08-01','','','',NULL,'',NULL,'Pending','2026-03-10 09:30:00',NULL,'Waiting on income verification.'),(2,'A1025','Marcus Lee','marcus@example.com','240-555-0102',4,'2026-08-15','','','',NULL,'',NULL,'Approved','2026-03-10 10:15:00',2,'Approved by leasing office.'),(3,'A1026','Ava Williams','ava@example.com','240-555-0103',1,'2026-09-01','','','',NULL,'',NULL,'Deposit Paid','2026-03-11 11:45:00',3,'Deposit received and unit held.'),(4,'A5224','Test One','test11@umd.edu','4436161455',1,'2026-04-22','118888019','testmom','4436161456',NULL,'',NULL,'Pending','2026-04-12 10:11:02',NULL,NULL),(5,'A3282','Test Two','test12@umd.edu','4436161457',2,'2026-04-29','118888020','testtwomom','4436161458',NULL,'',NULL,'Pending','2026-04-12 10:58:28',NULL,NULL),(6,'A1379','Test Three','test13@umd.edu','1112223333',3,'2026-04-29','1112223333','testdad','1112223334',NULL,'instance/application_uploads/70105cbe06fd4c17a39fb6d9934e38e7_IMG_0922.jpeg',NULL,'Pending','2026-04-12 11:25:17',NULL,NULL);
/*!40000 ALTER TABLE `applications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `floorplans`
--

DROP TABLE IF EXISTS `floorplans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `floorplans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `rent` int NOT NULL,
  `bedrooms` int NOT NULL,
  `bathrooms` int NOT NULL,
  `size` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `floorplans`
--

LOCK TABLES `floorplans` WRITE;
/*!40000 ALTER TABLE `floorplans` DISABLE KEYS */;
INSERT INTO `floorplans` VALUES (1,'4B/4B',974,4,4,1189),(2,'4B/2B',888,4,2,1493),(3,'2B/2B S',1082,2,2,785),(4,'2B/2B D',1118,2,2,991);
/*!40000 ALTER TABLE `floorplans` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `leases`
--

DROP TABLE IF EXISTS `leases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `leases` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lease_code` varchar(20) NOT NULL,
  `resident_user_id` int NOT NULL,
  `unit_id` int NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `monthly_rent` decimal(10,2) NOT NULL,
  `security_deposit` decimal(10,2) NOT NULL,
  `status` enum('Pending','Active','Ended') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_leases_code` (`lease_code`),
  KEY `fk_leases_user` (`resident_user_id`),
  KEY `fk_leases_unit` (`unit_id`),
  CONSTRAINT `fk_leases_unit` FOREIGN KEY (`unit_id`) REFERENCES `units` (`id`),
  CONSTRAINT `fk_leases_user` FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `leases`
--

LOCK TABLES `leases` WRITE;
/*!40000 ALTER TABLE `leases` DISABLE KEYS */;
INSERT INTO `leases` VALUES (1,'L2045',2,1,'2026-01-01','2026-12-31',1082.00,1082.00,'Active');
/*!40000 ALTER TABLE `leases` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `maintenance_requests`
--

DROP TABLE IF EXISTS `maintenance_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `maintenance_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_code` varchar(20) NOT NULL,
  `resident_user_id` int NOT NULL,
  `lease_id` int NOT NULL,
  `category` varchar(100) NOT NULL,
  `issue_title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `priority` enum('Low','Medium','High','Urgent') NOT NULL,
  `status` enum('Open','Assigned','In Progress','Closed') NOT NULL DEFAULT 'Open',
  `created_at` datetime NOT NULL,
  `attachment_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_maintenance_requests_code` (`request_code`),
  KEY `fk_requests_user` (`resident_user_id`),
  KEY `fk_requests_lease` (`lease_id`),
  CONSTRAINT `fk_requests_lease` FOREIGN KEY (`lease_id`) REFERENCES `leases` (`id`),
  CONSTRAINT `fk_requests_user` FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `maintenance_requests`
--

LOCK TABLES `maintenance_requests` WRITE;
/*!40000 ALTER TABLE `maintenance_requests` DISABLE KEYS */;
INSERT INTO `maintenance_requests` VALUES (1,'MR501',2,1,'Plumbing','Leaking sink','Resident reported steady water leaking from the kitchen sink pipe under the cabinet.','High','Open','2026-03-11 08:15:00','plumbing-photo.jpg'),(2,'MR502',2,1,'HVAC','Broken AC','Air conditioning unit is running but not cooling the apartment properly.','High','In Progress','2026-03-10 09:10:00','ac-unit-ticket.pdf'),(3,'MR503',2,1,'Electrical','Light fixture out','Bedroom ceiling light fixture is not turning on even after bulb replacement.','Low','Assigned','2026-03-09 14:35:00','electrical-note.docx');
/*!40000 ALTER TABLE `maintenance_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `payments`
--

DROP TABLE IF EXISTS `payments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `payment_code` varchar(20) NOT NULL,
  `lease_id` int NOT NULL,
  `resident_user_id` int NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `method` enum('Card','Bank Transfer','Cash','Check') NOT NULL,
  `status` enum('Pending','Paid','Failed','Resolved') NOT NULL,
  `payment_date` date DEFAULT NULL,
  `confirmation_number` varchar(30) DEFAULT NULL,
  `notes` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payments_code` (`payment_code`),
  KEY `fk_payments_lease` (`lease_id`),
  KEY `fk_payments_user` (`resident_user_id`),
  CONSTRAINT `fk_payments_lease` FOREIGN KEY (`lease_id`) REFERENCES `leases` (`id`),
  CONSTRAINT `fk_payments_user` FOREIGN KEY (`resident_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `payments`
--

LOCK TABLES `payments` WRITE;
/*!40000 ALTER TABLE `payments` DISABLE KEYS */;
INSERT INTO `payments` VALUES (1,'P1001',1,2,1250.00,'Card','Pending','2026-03-10','CNF88214','Resident contacted office about delayed processing.'),(2,'P1002',1,2,1300.00,'Bank Transfer','Paid','2026-03-09','CNF88215','Payment completed successfully and receipt was sent.'),(3,'P1003',1,2,1180.00,'Card','Failed','2026-03-08','CNF88216','Card declined. Resident needs to update payment method.');
/*!40000 ALTER TABLE `payments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `staff_schedule`
--

DROP TABLE IF EXISTS `staff_schedule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `staff_schedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `staff_user_id` int NOT NULL,
  `shift_date` date NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `assignment_note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_staff_schedule_user` (`staff_user_id`),
  CONSTRAINT `fk_staff_schedule_user` FOREIGN KEY (`staff_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `staff_schedule`
--

LOCK TABLES `staff_schedule` WRITE;
/*!40000 ALTER TABLE `staff_schedule` DISABLE KEYS */;
INSERT INTO `staff_schedule` VALUES (1,3,'2026-03-14','08:00:00','17:00:00','Cover Buildings 100 and 200.'),(2,3,'2026-03-15','08:00:00','17:00:00','Handle scheduled work orders.'),(3,3,'2026-03-16','09:00:00','18:00:00','Follow-up repairs and new assignments.');
/*!40000 ALTER TABLE `staff_schedule` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `units`
--

DROP TABLE IF EXISTS `units`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `units` (
  `id` int NOT NULL AUTO_INCREMENT,
  `building` varchar(20) NOT NULL,
  `unit_number` varchar(20) NOT NULL,
  `floorplan_id` int NOT NULL,
  `status` enum('Available','Occupied','Reserved','Maintenance') NOT NULL DEFAULT 'Available',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_units_unit_number` (`unit_number`),
  KEY `fk_units_floorplan` (`floorplan_id`),
  CONSTRAINT `fk_units_floorplan` FOREIGN KEY (`floorplan_id`) REFERENCES `floorplans` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `units`
--

LOCK TABLES `units` WRITE;
/*!40000 ALTER TABLE `units` DISABLE KEYS */;
INSERT INTO `units` VALUES (1,'Building 100','101A',3,'Occupied'),(2,'Building 200','235B',4,'Reserved'),(3,'Building 400','402C',1,'Available'),(4,'Building 200','214C',2,'Maintenance');
/*!40000 ALTER TABLE `units` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('resident','admin','staff','prospect') DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'Admin1','admin1@umd.edu','scrypt:32768:8:1$4nAi86mEzIGtrRHj$74bb26a9020de36579155370c9a9eee4953e56eb59fccb75aa9755a758e804a3598a52c6ce67db34250849fa60f80e8cbc6d6b7a0beb60cc6e1e34cdcbd969d4','admin'),(2,'Resident1','resident1@umd.edu','scrypt:32768:8:1$U2XzVOzxdUaIOl9j$5f3dc6a2cc29f1a82d4d03e7109fd51833a8a80090a7339d14370a0f1acb60047888c9c7ecd42d82e8359aca4fec33c8817869f0f8096c8ab8c5325aeffdad61','resident'),(3,'Staff1','staff1@umd.edu','scrypt:32768:8:1$TXOwFe5N00ygkQxq$e455c323077ba577624d34b8c611e925ef8df70d2ef3396c351aad7e2cc051c1ae08686f8640581717a46b9b67e1d1c11ed1dc7b7391efab6f4d3f0e5e682b20','staff'),(4,'Admin2','admin2@umd.edu','scrypt:32768:8:1$4PWfXsiBiXZx8yIp$f20fb16ef05a8179d33f784d1991b4802c10ebdc3a4c1f636fc60ddd0e786449acc21c9d3e03731ddee6e8beeb06e9c3aa2e9ecd5423b4df9b1849df33a05d4b','admin'),(5,'Prospect1','prospect1@umd.edu','scrypt:32768:8:1$kIBtPQFFm4wyvKtw$da604e2dc7b6f0c8cea35f17e80f81265a5261056ddded0372aaae4546ecb2e8d6585d37cce8958698c6d676e471113b536955e2450fe61a560f2e0c9244d8e5','resident'),(6,'Staff2','staff2@umd.edu','scrypt:32768:8:1$YzUivJnOhVddsM4d$532a7603bdd3c8f3f1a9886cddaa6ac7865b05a87130b50dd6575a5d00e0273a7ed30b1f9e6764d0dd189da520f40f5d817daf5d4c12b783e089fb478a1500d1','staff'),(8,'Test One','test11@umd.edu','scrypt:32768:8:1$5C7qyzK8MpdWIWfz$0209f6f5b71d10043f58de748f7268405802d9dd9594c72d3785ecf3533d5431acf5f1c1cfb2894492f547de8dc9642d9898751c458d5fefdc976ca743b118d8','prospect'),(9,'Test Two','test12@umd.edu','scrypt:32768:8:1$DNR52po2WQGnErkW$9d094ef01b56bb05cbb696d907255a32d4fac4b4c0fae46d33d86beaa7674c909156d5de9ba805d2d9da4b252bfc7cd30bd6988169da5ab7824a0373e2ee587a','prospect'),(10,'Test Three','test13@umd.edu','scrypt:32768:8:1$WBnOpDkaeuX89YQR$c987f1c75c7c4a2ce14dc3f2001e8c20c79ece90638f910092b2eabde226ae544e468df724058f3f230041059895c476830c9315b9df8cde846a5267825850eb','prospect');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `work_orders`
--

DROP TABLE IF EXISTS `work_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `work_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `work_order_code` varchar(20) NOT NULL,
  `request_id` int NOT NULL,
  `assigned_staff_id` int NOT NULL,
  `scheduled_date` date DEFAULT NULL,
  `time_window` varchar(50) DEFAULT NULL,
  `status` enum('Open','Assigned','In Progress','Closed') NOT NULL,
  `notes` text,
  `closed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_work_orders_code` (`work_order_code`),
  KEY `fk_work_orders_request` (`request_id`),
  KEY `fk_work_orders_staff` (`assigned_staff_id`),
  CONSTRAINT `fk_work_orders_request` FOREIGN KEY (`request_id`) REFERENCES `maintenance_requests` (`id`),
  CONSTRAINT `fk_work_orders_staff` FOREIGN KEY (`assigned_staff_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `work_orders`
--

LOCK TABLES `work_orders` WRITE;
/*!40000 ALTER TABLE `work_orders` DISABLE KEYS */;
INSERT INTO `work_orders` VALUES (1,'WO501',1,3,'2026-03-14','8:00 AM - 10:00 AM','Open','Assigned to morning plumbing block.',NULL),(2,'WO502',2,3,'2026-03-14','10:00 AM - 12:00 PM','In Progress','Needs HVAC follow-up after initial inspection.',NULL),(3,'WO503',3,3,'2026-03-15','1:00 PM - 3:00 PM','Assigned','Bring replacement fixture and tester.',NULL);
/*!40000 ALTER TABLE `work_orders` ENABLE KEYS */;
UNLOCK TABLES;
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-12 11:38:02
